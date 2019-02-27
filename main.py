import logging
from multiprocessing.pool import ThreadPool
import os
import pickle
import sys
from datetime import datetime, timezone
from ftplib import FTP
from hashlib import sha1
from pathlib import Path

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer


"""
	TODO: Add logic for deletion of files from server -> client
"""


class Server(ThreadedFTPServer):
    def __init__(self, ip="127.0.0.1", port=9090, directory=os.getcwd()):
        """
			Initmethod initializes ftp server
		"""
        os.chdir(directory)
        # Utility function to refresh db
        genAndDump = lambda x: self.dumpDB(self.generateDB())

        # Logic for authentication
        authorizer = DummyAuthorizer()

        # TODO: Replace with unique username,password for unique homedirs
        authorizer.add_user("user", "12345", homedir=directory, perm="elradfmw")

        self.cwd = Path(directory)
        handler = FTPHandler
        handler.authorizer = authorizer
        handler.on_disconnect = genAndDump  # Refresh DB on close
        handler.on_connect = genAndDump  # Refresh DB on connect

        # Configure ip, port & Authentication for server
        super().__init__((ip, port), handler)

    def generateDB(self):
        """
			Creates a dictionary of directory tree(all files) in dir(default=current dir):
			key: Complete file path.
					EG: ./dir1/dir2/file.ext
			value: sha1sum of the respective file
		"""
        try:
            os.mkdir(self.cwd / ".sync")
            logging.info("Created .sync dir")
        except FileExistsError:
            pass

            # Create a list of all files in cwd
        flat_files = [
            (path + "/" + File).replace("\\", "/")
            for path, _, fileNames in os.walk(".")
            for File in fileNames
            if path != "./.sync" and path != ".\\.sync"
        ]

        # A helper function that stores SHA1 hash of given file in db
        def calcHash(File):
            with open(File, "rb") as f:
                db[File] = sha1(f.read()).hexdigest()

        db = {}

        # Start 5 threads, to perform hashing
        pool = ThreadPool(processes=5)
        pool.map(calcHash, flat_files)
        pool.close()

        logging.debug("db = " + str(db))
        return db

    def dumpDB(self, db):
        """
			Writes db  dictionary to ./.sync/sync
		"""
        with open(self.cwd / ".sync/sync", "wb") as f:
            pickle.dump(db, f)
        logging.info("Successfully written db")


"""
	TODO:
	1) Configuration for 1-way or 2-way sync,
		1-way: Disable uploads
"""


class Client(Server):
    def __init__(
        self,
        ip="localhost",
        port=9090,
        user="user",
        password="12345",
        logging_level=logging.INFO,
        directory=os.getcwd(),
    ):
        """
			Initiate ftp connections to ip:port
			with user:password
			directory is local directory that represents remote directory
		"""
        logging.basicConfig(level=logging_level)
        os.chdir(directory)
        self.cwd = Path(directory)

        self.ftp = FTP("")
        self.ftp.connect(ip, port)

        logging.info("Logging in with {}:{}".format(user, password))
        self.ftp.login(user=user, passwd=password)

    def get_db(self):
        """
			Open sync and store in db (previous)
				If doesn't exist, generate and return
			Overwrite sync with remote sync file 
				Read remote_sync file to remote dict
		"""
        # Check for previous db
        if os.path.exists(self.cwd / "./.sync/sync"):
            with open(self.cwd / "./.sync/sync", "rb") as f:
                db = pickle.load(f)
        else:
            # Else generate
            db = self.db = self.generateDB()

            # Get remote db, overwrite local sync file
        self.downloadFile("./.sync/sync")
        with open(self.cwd / "./.sync/sync", "rb") as f:
            remote = pickle.load(f)
        logging.debug("db = {}\nremote = {}".format(db, remote))
        return db, remote

    def deleteFile(self, filename):
        # TODO: Add logic to delete empty directories
        logging.info("Deleting from  remote " + filename)
        self.ftp.delete(filename[2:])  # 2: Is to remove './'

    def uploadFile(self, filename):
        try:
            self.ftp.storbinary("STOR " + filename, open(self.cwd / filename, "rb"))
        except:
            tmp_list = os.path.dirname(filename).split("/")
            if len(tmp_list) == 1:
                tmp_list = tmp_list[0].split("\\")
            parent = ""
            for d in tmp_list:
                try:
                    self.ftp.mkd(parent + d)
                except:
                    pass
                parent += d + "/"
            self.ftp.storbinary(
                "STOR " + filename.replace("\\", "/"), open(self.cwd / filename, "rb")
            )
        logging.info("Uploaded " + filename)

    def downloadFile(self, filename):
        # Create directory if doesn't exist
        if not os.path.exists(os.path.dirname(self.cwd / filename)):
            os.makedirs(os.path.dirname(self.cwd / filename))

        localfile = open(self.cwd / filename, "wb")
        self.ftp.retrbinary("RETR " + filename, localfile.write, 1024)
        localfile.close()
        logging.info("Downloaded " + filename)

    def getTimestamp(self, file_name):
        """
			Get unix timestamp (since epoch) from remote system
			of given file_name
			Otherwise None
		"""
        file_name = file_name[2:]
        x = self.ftp.mlsd("", ["modify"])
        # Since mlsd returns tuple with modify time as UTC, logic to convert it
        for f, mtime in x:
            if f == file_name:
                ts = mtime["modify"]
                return (
                    datetime.strptime(ts, "%Y%m%d%H%M%S")
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )

    def sync(self):
        """
			This function will sync remote and local dir
			TODO: Deletion of remote files on local
		"""
        prev_db, remote = self.get_db()  # Initialize remote_db and prev_db
        db = self.generateDB()  # Get a fresh copy of current DB
        perfect_files = []
        for i in db:
            if prev_db.get(i, False):
                # Check if file has been deleted
                # A file is considered deleted if it exists in prev db but does
                # not exist in current db

                # Note this removes files which are 100% known not deleted
                # Actual deletion happens later
                del prev_db[i]
            if db[i] == remote.get(i):
                # Exactly same sha1hash
                perfect_files.append(i)
            elif i not in remote:
                # Missing files on remote
                # Exists on local not on remote
                self.uploadFile(i)
            else:
                # SHA1 mismatch. Sync according to newer file
                perfect_files.append(i)
                if self.getTimestamp(i) > os.stat(self.cwd / i).st_mtime:
                    logging.info("Downloading {} since new".format(i))
                    self.downloadFile(i)
                else:
                    logging.info("Uploading {} since new".format(i))
                    self.uploadFile(i)

        for i in prev_db:
            # Delete files from remote
            self.deleteFile(i)
            del remote[i]
        for i in perfect_files:
            del remote[i]
        for i in remote:
            # Download missing files on local
            self.downloadFile(i)
            # Write current DB to file
        self.dumpDB(db)


# Client
if sys.argv[1].lower() == "c":
    c = Client(directory=sys.argv[2])
    c.sync()
    c.ftp.quit()
# Server
if sys.argv[1].lower() == "s":
    Server(directory=sys.argv[2]).serve_forever()

