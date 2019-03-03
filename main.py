import logging
import json
from multiprocessing.pool import ThreadPool
from multiprocessing import Process
import os
import socket
import pickle
import sys
from datetime import datetime, timezone
from ftplib import FTP
from hashlib import sha1
from pathlib import Path

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import ThreadedFTPServer


class Server:
    def __init__(self, ip="127.0.0.1", port=9090, config_file="server.json"):
        """
			Initmethod initializes ftp server
		"""
        with open(config_file, "r") as f:
            self.config = json.load(f)

            # Logic for authentication
        authorizer = DummyAuthorizer()

        for user, details in self.config.items():
            authorizer.add_user(
                user,
                details["password"],
                homedir=details["local_path"],
                perm=details["perms"],
            )

        handler = FTPHandler
        handler.authorizer = authorizer
        handler.on_disconnect = self.genAndDump  # Refresh DB on close
        handler.on_login = self.on_login

        # Configure ip, port & Authentication for server
        self.server = ThreadedFTPServer((ip, port), handler)

    def serve_forever(self):
        self.server.serve_forever()

    def genAndDump(self):
        db = {}
        db = self.generateDB()
        if os.path.exists(self.cwd / ".sync/sync"):
            with open(self.cwd / ".sync/sync", "rb") as f:
                prev_db = pickle.load(f)
        else:
            self.dumpDB(db)
            return
        if prev_db == db:
            return
        if os.path.exists(self.cwd / ".sync/toDelete"):
            with open(self.cwd / ".sync/toDelete", "rb") as f:
                self.to_delete = pickle.load(f)
        else:
            self.to_delete = {}
        for i in prev_db:
            if i not in db:
                self.to_delete[i] = prev_db[i]
        with open(self.cwd / ".sync/toDelete", "wb") as f:
            pickle.dump(self.to_delete, f)
        self.dumpDB(db)

    def on_login(self, username):
        self.cwd = Path(self.config[username]["local_path"])
        self.genAndDump()

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
        prev = os.getcwd()
        os.chdir(self.cwd)

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
        os.chdir(prev)
        return db

    def dumpDB(self, db):
        """
			Writes db  dictionary to ./.sync/sync
		"""
        with open(self.cwd / ".sync/sync", "wb") as f:
            pickle.dump(db, f)
        logging.info("Successfully written db")


class Client(Server):
    def __init__(
        self,
        ip="localhost",
        port=9090,
        read_only=False,
        user="user",
        password="12345",
        logging_level=logging.INFO,
        local_path=os.getcwd(),
    ):
        """
			Initiate ftp connections to ip:port
			with user:password
			directory is local directory that represents remote directory
			When read_only mode is set, upload and delete are disabled
		"""
        logging.basicConfig(level=logging_level)
        self.cwd = Path(local_path)
        os.chdir(self.cwd)
        self.read_only = read_only
        if self.read_only:
            logging.warning(
                "READ-ONLY mode all files that are modified will be overwritten. Please backup if necessary"
            )
        self.db = None

        self.ftp = FTP("")
        try:
            self.ftp.connect(ip, port, timeout=30)
        except OSError:
            logging.info("Failed to connect to {}:{}".format(ip, port))
            raise OSError

        logging.info("Logging in with {}:{}".format(user, password))
        self.ftp.login(user=user, passwd=password)

    def get_db(self):
        """
			Open sync and store in db (previous)
				If doesn't exist, generate and return
			Overwrite sync with remote sync file 
				Read remote_sync file to remote dict
		"""
        # Get remote db, overwrite local sync file
        if os.path.exists(self.cwd / "./.sync/sync"):
            with open(self.cwd / "./.sync/sync", "rb") as f:
                local = pickle.load(f)
        else:
            local = {}
        self.downloadFile("./.sync/sync")
        with open(self.cwd / "./.sync/sync", "rb") as f:
            remote = pickle.load(f)
        with open(self.cwd / "./.sync/sync", "wb") as f:
            pickle.dump(local, f)
        return remote

    def deleteFile(self, filename):
        if self.read_only:
            logging.info(
                "Skipped {}, since read-only-mode set by server".format(filename)
            )
            return
            # TODO: Add logic to delete empty directories
        logging.info("Deleting from  remote " + filename)
        self.ftp.delete(filename[2:])  # 2: Is to remove './'

    def uploadFile(self, filename):
        if self.read_only:
            logging.info(
                "Skipped {}, since read-only-mode set by server".format(filename)
            )
            return
        try:
            self.ftp.storbinary("STOR " + filename, open(self.cwd / filename, "rb"))
        except:
            # Create directory(s) if non existent
            logging.debug("Missing file(s) on remote: " + filename)
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

    def getDelete(self):
        """
			Get a dictionary of deleted files from remote
			key=file_path
			value=SHA1 hash
		"""
        local_delete = {}
        delete = {}
        if os.path.exists(self.cwd / ".sync/toDelete"):
            with open(self.cwd / ".sync/toDelete", "rb") as f:
                local_delete = pickle.load(f)
        try:
            self.downloadFile("./.sync/toDelete")
            with open(self.cwd / ".sync/toDelete", "rb") as f:
                delete = pickle.load(f)
        except:
            pass
        with open(self.cwd / ".sync/toDelete", "wb") as f:
            pickle.dump(local_delete, f)
        return local_delete, delete

    def sync(self):
        """
			This function will sync remote and local dir
		"""
        remote = self.get_db()  # Initialize remote_db and prev_db
        db = self.generateDB()
        perfect_files = []
        self.genAndDump()
        local_delete, remote_delete = self.getDelete()
        for i in db:

            if db[i] == remote.get(i):
                # Exactly same sha1hash
                perfect_files.append(i)
            elif remote_delete.get(i) == db[i]:
                # Check if file is marked deleted on remote
                logging.info("Deleting: " + i)
                os.remove(self.cwd / i)
            elif i not in remote:
                # Missing files on remote
                # Exists on local not on remote
                self.uploadFile(i)
            else:
                # SHA1 mismatch. Sync according to newer file
                perfect_files.append(i)
                if (
                    self.read_only
                    or self.getTimestamp(i) > os.stat(self.cwd / i).st_mtime
                ):
                    self.downloadFile(i)
                else:
                    self.uploadFile(i)

        for i in perfect_files:
            del remote[i]
        for i in remote:
            # Download missing files on local
            if local_delete.get(i) == remote[i]:
                self.deleteFile(i)
            else:
                self.downloadFile(i)
        self.dumpDB(db)
        self.ftp.quit()


# Client
if sys.argv[1].lower() == "c":
    with open("client.json", "r") as f:
        config = json.load(f)
    for ip in config:
        try:
            Client(ip=ip, **config[ip]).sync()
        except OSError:
            logging.info("Skipping " + ip)
# Server
if sys.argv[1].lower() == "s":
    Server(ip="0.0.0.0").serve_forever()

