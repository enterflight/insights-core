"""
LogrotateConfAll - Combiner for logrotate configuration
=======================================================
Combiner for accessing all the logrotate configuration files.  It collects all
LogrotateConf generated from each single logrotate configuration file.

There may be multiple logrotate configuration, and the main configuration file is
``/etc/logrotate.conf``.  Only the options defined in this file are global
options, and all other options (if there are) will be discarded.

"""
import operator
import os

from fnmatch import fnmatch
from insights.core import ConfigCombiner
from insights.core.plugins import combiner
from insights.parsers.logrotate_conf import LogrotateConf, LogRotateConfPEG
from insights.parsr.query import eq


@combiner(LogrotateConf)
class LogrotateConfAll(object):
    """
    Class for combining all the logrotate configuration files.

    Sample files::

        # /etc/logrotate.conf:
            compress
            rotate 7

            /var/log/messages {
                rotate 5
                weekly
                postrotate
                            /sbin/killall -HUP syslogd
                endscript
            }

        # /etc/logrotate.d/httpd
            "/var/log/httpd/access.log" /var/log/httpd/error.log {
                rotate 5
                mail www@my.org
                size=100k
                sharedscripts
                postrotate
                            /sbin/killall -HUP httpd
                endscript
            }

        # /etc/logrotate.d/newscrit
            /var/log/news/*.crit  {
                monthly
                rotate 2
                olddir /var/log/news/old
                missingok
                postrotate
                            kill -HUP `cat /var/run/inn.pid`
                endscript
                nocompress
            }

    Examples:
        >>> all_lrt.global_options
        ['compress', 'rotate']
        >>> all_lrt['rotate']
        '7'
        >>> '/var/log/httpd/access.log' in all_lrt.log_files
        True
        >>> all_lrt['/var/log/httpd/access.log']['rotate']
        '5'
        >>> all_lrt.configfile_of_logfile('/var/log/news/olds.crit')
        '/etc/logrotate.d/newscrit'
        >>> all_lrt.options_of_logfile('/var/log/httpd/access.log')['mail']
        'www@my.org'


    Attributes:
        data(dict): All parsed options and log files are stored in this
            dictionary
        global_options(list): List of global options defined in
            ``/etc/logrotate.conf``
        log_files(list): List of log files in all logrotate configuration files
    """
    def __init__(self, lrt_conf):
        self.data = {}
        self.global_options = []
        self.log_files = []
        self._file_map = {}

        for lrt in lrt_conf:
            self.data.update(lrt.data)
            if lrt.file_path == "/etc/logrotate.conf":
                self.global_options = lrt.options
            self.log_files.extend(lrt.log_files)
            self._file_map[lrt.file_path] = lrt.log_files

    def __contains__(self, item):
        return (item in self.global_options or
                any(fnmatch(item, f) for f in self.log_files))

    def __getitem__(self, item):
        if item in self.global_options:
            return self.data[item]
        return self.data.get(self._get_match_logfile(item))

    def _get_match_logfile(self, log_file, file_list=[]):
        file_list = self.log_files if not file_list else file_list
        for f in file_list:
            if fnmatch(log_file, f):
                return f

    def options_of_logfile(self, log_file):
        """
        Get the options of ``log_file``.

        Parameters:
            log_file(str): The log files need to check.

        Returns:
            dict: Dictionary contains the options of ``log_file``.  None when no
            such ``log_file``.
        """
        return self.data.get(self._get_match_logfile(log_file))

    def configfile_of_logfile(self, log_file):
        """
        Get the configuration file path in which the ``log_file`` is configured.

        Parameters:
            log_file(str): The log files need to check.

        Returns:
            dict: The configuration file path of ``log_file``.  None when no
            such ``log_file``.
        """
        for f, lfs in self._file_map.items():
            if self._get_match_logfile(log_file, lfs):
                return f


@combiner(LogRotateConfPEG)
class LogRotateConfTree(ConfigCombiner):
    """
    Exposes logrotate configuration through the parsr query interface.

    See the :py:class:`insights.core.ConfigComponent` class for example usage.
    """
    def __init__(self, confs):
        include = eq("include")
        main_file = "logrotate.conf"
        super(LogRotateConfTree, self).__init__(confs, main_file, include)

    @property
    def conf_path(self):
        return os.path.dirname(self.main.file_path)

    def find_matches(self, confs, pattern):
        results = []
        for c in confs:
            if os.path.isdir(pattern) and c.file_path.startswith(pattern):
                results.append(c)
            elif fnmatch(c.file_path, pattern):
                results.append(c)
        return sorted(results, key=operator.attrgetter("file_name"))
