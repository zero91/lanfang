"""Tools for running a bunch of tasks which may have dependency relationships. 
It can execute tasks efficiently in parallel if their dependency relationships
can be expressed as a topological graph.
"""
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from .common import TaskStatus
from .task_runner import TaskRunner
from . import progress_display

import sys
import time
import signal
import re
import os
import collections
import copy
import logging

class TaskDependencyManager(object):
    """Manage a batch of tasks' topological relations.

    """
    def __init__(self):
        self._m_dependency_info = collections.defaultdict(set)
        self._m_task_id = collections.defaultdict(list) # task_name => (initial ID, running ID)
        self._m_is_valid = None

    @classmethod
    def from_data(cls, task_depends_list):
        """Class method. Create a `TaskDependencyManager' object from `task_depends_list'.

        Parameters
        ----------
        task_depends_list: list
            A sequence of tasks, each item is in format (task_name, depends).

        Returns
        -------
        instance: TaskDependencyManager
            Instance constructed from input argument.

        """
        instance = cls()
        for task_name, depends in task_depends_list:
            instance.add_dependency(task_name, depends)
        return instance

    def add_dependency(self, task_name, depend_tasks=None):
        """Add one dependency relation.

        Parameters
        ----------
        task_name: str
            Task's name.

        depend_tasks: string/list/tuple/set/dict
            Tasks which need to be done before `task_name'.

        Returns
        -------
        instance: TaskDependencyManager
            Current instance's reference.

        Raises
        ------
        TypeError: If type of `depend_tasks' is not supported.

        """
        self._m_task_id[task_name] = [len(self._m_task_id), None]

        if depend_tasks is None or len(depend_tasks) == 0:
            depend_tasks_set = set()

        elif isinstance(depend_tasks, (list, tuple, set, dict)):
            depend_tasks_set = set(depend_tasks)

        elif isinstance(depend_tasks, str):
            depend_tasks_set = set(map(str.strip, depend_tasks.split(',')))

        else:
            self._m_task_id.pop(task_name)
            raise TypeError("depend_tasks's data type does not support")

        self._m_is_valid = None
        self._m_dependency_info[task_name] |= depend_tasks_set
        return self

    def get_dependency(self, task_name):
        """Get dependency tasks of `task_name'.

        Parameters
        ----------
        task_name: string
            Task's name

        Returns
        -------
        depend_set: set
            Set of jobs which need to be done before `task_name'.

        Raises
        ------
        KeyError: Can't find the task.

        """
        if task_name not in self._m_dependency_info:
            raise KeyError("Can't find task '%s'" % (task_name))
        return self._m_dependency_info[task_name]

    def get_tasks_info(self):
        """Get all tasks' informations.

        Returns
        -------
        is_valid: boolean
            Whether all tasks' relations is topological.

        tasks_info: collections.defaultdict
            All tasks' information. key is the task's name, value contains
                (initial_id, running_id, depend_set, reverse_depend_set)

        """
        self.is_topological()
        tasks = collections.defaultdict(list)
        for task_name, (initial_id, running_id) in self._m_task_id.items():
            tasks[task_name] = [initial_id, running_id, set(), set()]

        for task_name, depends_set in self._m_dependency_info.items():
            tasks[task_name][2] = copy.deepcopy(depends_set)
            for depend_task_name in depends_set:
                tasks[depend_task_name][3].add(task_name)
        return self._m_is_valid, tasks

    def is_topological(self):
        """Test whether current relations is topological.

        Returns
        -------
        is_topological: boolean
            True if current relations is topological, otherwise False.

        """
        if self._m_is_valid is not None:
            return self._m_is_valid

        dependency_info = copy.deepcopy(self._m_dependency_info)
        reverse_dependency_info = collections.defaultdict(set)
        for name, depends_set in dependency_info.items():
            for depend in depends_set:
                reverse_dependency_info[depend].add(name)

        cur_task_id = 0
        while len(dependency_info) > 0:
            ready_list = list()
            for name, depend_set in dependency_info.items():
                if len(depend_set) == 0:
                    ready_list.append(name)

            if len(ready_list) == 0:
                self._m_is_valid = False
                return False

            for name in sorted(ready_list, key=lambda name: self._m_task_id[name][0]):
                self._m_task_id[name][1] = cur_task_id
                cur_task_id += 1
                if name in reverse_dependency_info:
                    for depend_name in reverse_dependency_info[name]:
                        dependency_info[depend_name].remove(name)
                    reverse_dependency_info.pop(name)
                dependency_info.pop(name)
        self._m_is_valid = True
        return True

    def __parse_single_task_id(self, task_str):
        if task_str.isdigit():
            return int(task_str)

        elif task_str in self._m_task_id:
            return self._m_task_id[task_str][1]

        elif len(task_str) > 0:
            raise ValueError("task str's format does not support [{0}]".format(task_str))

        return None

    def parse_tasks(self, tasks_str):
        """Parse a string into full tasks with its dependency relations.

        Parameters
        ----------
        tasks_str: string
            Suppose we have a batch of tasks as [(0, 'a'), (1, 'b'), (2, 'c'), ..., (25, 'z')].

            `tasks_str' support following formats:
            (1) "-3,5,7-10-2,13-16,19-".
                "-3" means range from 0(start) to 3, which is "0,1,2,3".
                "7-10-2" means range from 7 to 10, step length 2, which is "7,9".
                "13-16" means range from 13 to 16, step length 1, which is "13,14,15,16."
                "19-" mean range from 19 to 25(end), which is "19,20,21,22,23,24,25".

            (2) "1-4,x,y,z"
                "1-4" mean range from 1 to 4, which is "1,2,3,4"
                "x" mean task 'x', task id is 23.
                "y" mean task 'y', task id is 24.
                "z" mean task 'z', task id is 25.
                So, above string mean jobs "1,2,3,4,23,24,25".

        Returns
        -------
        dependency_manager: TaskDependencyManager
            TaskDependencyManager which contains all the jobs specified by input argument.

        """
        self.is_topological()
        if tasks_str is None:
            return copy.deepcopy(self)

        tasks_set = set()
        for seg in tasks_str.split(','):
            seg = seg.strip()
            if seg == "":
                continue

            item_list = seg.split('-')
            if len(item_list) == 1:
                tid = self.__parse_single_task_id(item_list[0])
                if tid is not None and 0 <= tid < len(self._m_task_id):
                    tasks_set.add(tid)

            elif 2 <= len(item_list) <=  3:
                start = self.__parse_single_task_id(item_list[0])
                stop = self.__parse_single_task_id(item_list[1])
                if len(item_list) == 3:
                    step = self.__parse_single_task_id(item_list[2])
                else:
                    step = 1

                if start is None:
                    start = 0
                if stop is None:
                    stop = len(self._m_task_id) - 1
                if step is None:
                    step = 1
                tasks_set |= set(range(start, stop + 1, step))

            else:
                raise ValueError('format of the task str [{0}] does not support'.format(seg))

        valid_tasks_list = list(filter(lambda t: self._m_task_id[t][1] in tasks_set,
                                       self._m_task_id))
        valid_tasks_list.sort(key=lambda t: self._m_task_id[t][0])

        valid_tasks_set = set(valid_tasks_list)
        valid_tasks_depends = list()
        for task in valid_tasks_list:
            valid_tasks_depends.append(valid_tasks_set & self._m_dependency_info[task])
        return self.__class__.from_data(zip(valid_tasks_list, valid_tasks_depends))


class MultiTaskRunner(object):
    """Run multiple tasks.

    It maintains a set of tasks, and run the tasks according to their topological relations.

    Parameters
    ----------
    log_path: str/None/subprocess.PIPE
        The directory which used to save logs. Default to be None, the process's file
        handles will be inherited from the parent. Log will be write
        to filename specified by each task's name end up with "stdout"/"stderr".

    render_arguments: dict
        Dict which used to replace tasks' parameter for its true value.

    parallel_degree: integer
        Parallel degree of this task. At most `parallel_degree' of the tasks will be run
        simultaneously.

    retry: integer
        Try executing each task retry times until succeed.

    """
    def __init__(self, log_path=None, render_arguments=None, parallel_degree=-1, retry=1):
        if log_path is not None:
            self._m_log_path = os.path.realpath(log_path)
        else:
            self._m_log_path = None

        if render_arguments is None:
            self._m_render_arguments = dict()
        elif isinstance(render_arguments, dict):
            self._m_render_arguments = render_arguments
        else:
            raise ValueError("type of parameter `render_arguments' does not supported")

        self._m_parallel_degree = parallel_degree
        self._m_retry = retry

        self._m_dependency_manager = TaskDependencyManager()
        self._m_task_runner_dict = dict()
        self._m_running_task_set = set()
        self._m_started = False

    def add(self, command, name=None, depends=None, append_log=True, **popen_kwargs):
        """Add a new task.

        Parameters
        ----------
        command: list/str
            The command which need to be executed.
            It has the same meaning as TaskRunner's command parameter.

        name: str
            The name of the task. Best using naming method of programming languages,
            for it may be used to create log files on disk.

        depends: str/list/set/dict
            List of depended jobs' name.
            If this is a string which is the concatenation of the names of all the tasks which
            must be executed ahead of this task. Separated by a single comma(',').

        append_log: boolean
            Append to log file if set True, otherwise clear old content.

        popen_kwargs: dict
            It has the same meaning as Popen's arguments.

        Returns
        -------
        instance: MultiTaskRunner
            Reference for current instance.

        Raises
        ------
        KeyError: If the task is already exists.

        """
        if name in self._m_task_runner_dict:
            raise KeyError("Task {0} is already exists!".format(name))

        if isinstance(self._m_log_path, str):
            if not os.path.exists(self._m_log_path):
                os.makedirs(self._m_log_path)

            for sname in ["stdout", "stderr"]:
                if sname in popen_kwargs:
                    continue
                popen_kwargs[sname] = open("%s/%s.%s" % (self._m_log_path, name, sname),
                                           'a+' if append_log is True else 'w+')

        runner = TaskRunner(command, name=name, retry=self._m_retry, **popen_kwargs)
        self._m_task_runner_dict[runner.name] = [TaskStatus.WAITING, runner]
        self._m_dependency_manager.add_dependency(runner.name, depends)
        return self

    def adds(self, tasks_str):
        """Add tasks from a string.

        Parameters
        ----------
        tasks_str: string
            The string of the tasks, which is a python executable code.

        Returns
        -------
        instance: MultiTaskRunner
            Reference for current instance.

        Raises
        ------
        KeyError: Some of the arguments specified in `tasks_str' didn't provided.

        """
        render_arg_pattern = re.compile(r"\<\%=(.*?)\%\>")
        for match_str in re.findall(render_arg_pattern, tasks_str):
            match_str = match_str.strip()
            if match_str not in self._m_render_arguments:
                raise KeyError("missing value for render argument {0}".format(match_str))

        def __lookup_func(reg_match):
            return self._m_render_arguments[reg_match.group(1).strip()]
        tasks_str = render_arg_pattern.sub(__lookup_func, tasks_str)

        exec(tasks_str, {}, {'TaskRunner': self.add})
        return self

    def addf(self, tasks_fname, encoding="utf-8"):
        """Add tasks from a file.

        Parameters
        ----------
        tasks_fname : string
            The file's name of which contains tasks.

        encoding: string
            The encode of file content specified by `tasks_fname'.

        Returns
        -------
        instance: MultiTaskRunner
            Reference for current instance.

        """
        with open(tasks_fname, mode='r', encoding=encoding) as ftask:
            return self.adds(ftask.read())

    def lists(self, displayer=None):
        """List all tasks.

        Parameters
        ----------
        displayer: class Instance
            Class which can be used to display tasks status.

        Raises
        ------
        ValueError: If the tasks' relation is not topological.

        """
        if not self._m_dependency_manager.is_topological():
            raise ValueError("tasks's depenency relationships is not topological")

        if displayer is None:
            progress_display.TableProgressDisplay(self._m_dependency_manager,
                                                  self._m_task_runner_dict).display()
        else:
            displayer(self._m_dependency_manager, self._m_task_runner_dict).display()

    def run(self, tasks=None, verbose=False, displayer=None):
        """Run tasks.

        Parameters
        ----------
        tasks : str
            The tasks which needed to be executed, sepecified by string seperated by one comma.
            Supported format is the same as method:
                    `TaskDependencyManager.parse_tasks'

        verbose: boolean
            Print verbose information.

        displayer: class Instance
            Class instance which can display tasks information in the managed way.

        Returns
        -------
        result : integer
            0 for success, otherwise nonzero.

        Raises
        ------
        RuntimeError: If the tasks set is not a topological one or has been exected already.

        Notes
        -----
            Should only be executed once.

        """
        if self._m_started:
            raise RuntimeError("{0} should be executed only once".format(self.__class__.__name__))

        if not self._m_dependency_manager.is_topological():
            raise RuntimeError("tasks' dependency relationships is not topological")

        self._m_started = True

        signal.signal(signal.SIGINT, self.__kill_signal_handler)
        signal.signal(signal.SIGTERM, self.__kill_signal_handler)

        tasks_info = self._m_dependency_manager.parse_tasks(tasks).get_tasks_info()[1]
        for task_name in self._m_task_runner_dict:
            if task_name not in tasks_info:
                self._m_task_runner_dict[task_name][0] = TaskStatus.DISABLED

        if displayer is None:
            displayer = progress_display.TableProgressDisplay(self._m_dependency_manager,
                                                              self._m_task_runner_dict)
        else:
            displayer = displayer(self._m_dependency_manager, self._m_task_runner_dict)

        ready_list = list()
        verbose and displayer.display()
        while True:
            for task_name, (initial_id, running_id, depends, rdepends) in tasks_info.items():
                if len(depends) == 0 and \
                            self._m_task_runner_dict[task_name][0] == TaskStatus.WAITING:
                    ready_list.append(task_name)
                    self._m_task_runner_dict[task_name][0] = TaskStatus.READY

            ready_list.sort(key=lambda task_name: tasks_info[task_name][1])
            while len(ready_list) > 0 and (self._m_parallel_degree < 0 or \
                    len(self._m_running_task_set) < self._m_parallel_degree):
                task_name = ready_list.pop(0)
                self._m_running_task_set.add(task_name)
                self._m_task_runner_dict[task_name][0] = TaskStatus.RUNNING
                self._m_task_runner_dict[task_name][1].start()

            for task_name in self._m_running_task_set.copy():
                if self._m_task_runner_dict[task_name][1].is_alive():
                    continue
                self._m_running_task_set.remove(task_name)

                ret_code = self._m_task_runner_dict[task_name][1].returncode
                if ret_code != 0:
                    self._m_task_runner_dict[task_name][0] = TaskStatus.FAILED
                    self.terminate()
                    displayer.display()
                    logging.critical("Task {0} failed, exit code {1}\n".format(task_name, ret_code))
                    return 1
                else:
                    self._m_task_runner_dict[task_name][0] = TaskStatus.DONE

                for depend_task_name in tasks_info[task_name][3]:
                    tasks_info[depend_task_name][2].remove(task_name)
                tasks_info.pop(task_name)

            verbose and displayer.display()
            if len(tasks_info) == 0 and len(self._m_running_task_set) == 0 and len(ready_list) == 0:
                break
            time.sleep(0.1)

        verbose and displayer.display()
        return 0

    def __kill_signal_handler(self, signum, stack):
        self.terminate()
        progress_display.TableProgressDisplay(
                self._m_dependency_manager, self._m_task_runner_dict).display()
        logging.info("Receive signal %d, all running processes are killed.", signum)
        exit(1)

    def terminate(self):
        """Terminate all running process."""
        for task_name in self._m_running_task_set.copy():
            self._m_task_runner_dict[task_name][1].terminate()
            self._m_task_runner_dict[task_name][0] = TaskStatus.KILLED
            self._m_running_task_set.remove(task_name)

    def get_task_runner(self, task_name):
        """Get running instance of `task_name'.

        Parameters
        ----------
        task_name: str
            Target task's name.

        Returns
        -------
        runner: TaskRunner
            Reference runner of `task_name'.

        """
        if task_name not in self._m_task_runner_dict:
            return None
        return self._m_task_runner_dict[task_name][1]

