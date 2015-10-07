import os
import time
import sqlite3
import threading
from queue import Queue


class Sql:

    def __init__(self, save_path, content_type):

        self._db_file = os.path.join(save_path, "testA.db")

        self.content_type = content_type
        self._setup_database()

        # Create queue for inserting into database to use
        self._sql_queue = Queue(maxsize=0)

        # Create a single thread to insert data into the database
        sql_worker = threading.Thread(target=self._add_to_db)
        sql_worker.setDaemon(True)
        sql_worker.start()

    def get_sql_queue(self):
        return self._sql_queue.qsize()

    def _setup_database(self):
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

    def _add_to_db(self):
        """
        As items are added to `_sql_queue` they are inserted into the db
        """
        conn = sqlite3.connect(self._db_file)
        with conn:
            cur = conn.cursor()
            while True:
                query = self._sql_queue.get()

                try:
                    # TODO: Check utc time to see if new day, if so create new db with new self.conn
                    if self.content_type == "t1":
                        cur.execute("INSERT INTO \
                            t1 (name, created_utc, link_id, subreddit, subreddit_id, author, parent_id, json) \
                            VALUES (?,?,?,?,?,?,?,?)", query)
                    elif self.content_type == "t3":
                        cur.execute("INSERT INTO \
                            t3 (name, created_utc, domain, subreddit, subreddit_id, author, json) \
                            VALUES (?,?,?,?,?,?,?)", query)
                    # Save (commit) the changes
                    conn.commit()
                except sqlite3.IntegrityError:
                    # It tried to add a post that was already in the database
                    #   We do not care, so ignore it
                    pass

                self._sql_queue.task_done()
