import os
import sqlite3
import threading
from queue import Queue
from utils.general_utils import GeneralUtils


class Sql(GeneralUtils):

    def __init__(self, save_path, content_type):
        super().__init__()

        self.content_type = content_type

        self._db_path = save_path

        self.conn = None
        self.curr_day = None
        # When `True`, start checking the posts created time to see if we need a new db
        self._check_day = None
        self._set_check_day_true()

        # Create queue for inserting into database to use
        self._sql_queue = Queue(maxsize=0)

        # Create a single thread to insert data into the database
        sql_worker = threading.Thread(target=self._add_to_db)
        sql_worker.setDaemon(True)
        sql_worker.start()

    def get_sql_queue(self):
        return self._sql_queue.qsize()

    def _create_tables(self):
        # If we do not have a database file then create it
        # TODO: Check if we have the correct tables if the file DOES exists
        if not os.path.isfile(self._db_file):
            conn = sqlite3.connect(self._db_file)
            if self.content_type == "t1":
                conn.execute('''CREATE TABLE t1
                             (name           VARCHAR(20)     PRIMARY KEY,
                              created_utc    INTEGER         NOT NULL,
                              link_id        VARCHAR(20)     NOT NULL,
                              subreddit      VARCHAR(100)    NOT NULL,
                              subreddit_id   VARCHAR(20)     NOT NULL,
                              author         VARCHAR(100)    NOT NULL,
                              parent_id      VARCHAR(20)     NOT NULL,
                              json           TEXT            NOT NULL
                             );
                             ''')
            elif self.content_type == "t3":
                conn.execute('''CREATE TABLE t3
                             (name           VARCHAR(20)     PRIMARY KEY,
                              created_utc    INTEGER         NOT NULL,
                              domain         VARCHAR(100)    NOT NULL,
                              subreddit      VARCHAR(100)    NOT NULL,
                              subreddit_id   VARCHAR(20)     NOT NULL,
                              author         VARCHAR(100)    NOT NULL,
                              json           TEXT            NOT NULL
                             );
                             ''')

            conn.close()

    def sql_add_queue(self, query):
        """
        Add queries to a queue to be processed by _add_to_db()
        """
        # self._sql_queue.append(query)
        self._sql_queue.put(query)

    def _create_new_db(self, time):
        dt = self.get_datetime(time)
        self.curr_day = str(dt.day)
        year = str(dt.year)
        month = "%02d" % (dt.month,)
        day = "%02d" % (dt.day,)
        filename = year + "." + month + "." + day + "_" + self.content_type + ".db"
        self._db_file = os.path.join(self._db_path, filename)
        self._create_tables()
        self.conn = sqlite3.connect(self._db_file)
        self.cur = self.conn.cursor()

    def _check_need_new_db(self, time):
        dt = self.get_datetime(time)
        if str(dt.day) != self.curr_day:
            self._create_new_db(time)
            self._check_day = False

    def _timer_check_day(self):
        """
        Start checking if new day in n seconds
        """
        # Get seconds till midnight utc
        from datetime import datetime

        now_utc = datetime.utcnow()
        seconds_since_midnight = (now_utc - now_utc.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()

        seconds_till_midnight = abs(seconds_since_midnight - 86400)  # 86400 seconds in a day
        t_reload = threading.Timer(seconds_till_midnight - 60, self._set_check_day_true)
        t_reload.setDaemon(True)
        t_reload.start()

    def _set_check_day_true(self):
        self._check_day = True
        # Restart timmer
        self._timer_check_day()

    def _add_to_db(self):
        """
        As items are added to `_sql_queue` they are inserted into the db
        """

        if self._check_day is True:
            current_utc = self.get_utc_epoch()
            self._check_need_new_db(current_utc)

        with self.conn:
            while True:
                query = self._sql_queue.get()
                self._check_need_new_db(query[1])

                try:
                    # TODO: Check utc time to see if new day, if so create new db with new self.conn
                    if self.content_type == "t1":
                        self.cur.execute("INSERT INTO \
                            t1 (name, created_utc, link_id, subreddit, subreddit_id, author, parent_id, json) \
                            VALUES (?,?,?,?,?,?,?,?)", query)
                    elif self.content_type == "t3":
                        self.cur.execute("INSERT INTO \
                            t3 (name, created_utc, domain, subreddit, subreddit_id, author, json) \
                            VALUES (?,?,?,?,?,?,?)", query)
                    # Save (commit) the changes
                    self.conn.commit()
                except sqlite3.IntegrityError:
                    # It tried to add a post that was already in the database
                    #   We do not care, so ignore it
                    pass

                self._sql_queue.task_done()
