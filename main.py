import logging
import os, sys
from pathlib import Path
import pickle
from datetime import datetime, timezone
from ftplib import FTP
from hashlib import sha1
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


"""
    TODO:
    1) Create threads for sha1 as big files will take time
    2) Use threaded FTPServer 
    3) Write logic to create unique folder mappings eg
        dir2 = canjsk
        dir2/dir2 = ckamskm
        dir2/dir1 = safnj
        Which will be used as userID 
"""


class Server(FTPServer):
    def __init__(self, ip="127.0.0.1", port=9090, directory=os.getcwd()):
        genAndDump = lambda x: self.dumpDB(
            self.generateDB()
        )  # Utility function to refresh db on closed connection
        authorizer = DummyAuthorizer()
        # TODO: Replace with unique username,password for unique homedirs
        authorizer.add_user("user", "12345", homedir=directory, perm="elradfmw")
        self.cwd = Path(directory)

        handler = FTPHandler
        handler.authorizer = authorizer
        handler.on_disconnect = genAndDump  # Refresh DB on close
        handler.on_connect = genAndDump

        super().__init__((ip, port), handler)

    def generateDB(self,dir="."):
        """
            Creates a dictionary of directory tree(all files) in dir(default=current dir):
            key: Complete file path.
                    EG: ./dir1/dir2/file.ext
            value: sha1sum of the respective file
        """
        try:
            os.mkdir(self.cwd/'.sync')
            logging.info("Created .sync dir")
        except FileExistsError:
            pass
        flat_files = [
            path + "/" + File
            for path, _, fileNames in os.walk(dir)
            for File in fileNames
            if path != "./.sync"
        ]
        db = {}
        for File in flat_files:
            with open(File, "rb") as f:
                db[File] = sha1(f.read()).hexdigest()
        logging.debug("db = " + str(db))
        return db

    def dumpDB(self,db):
        """
            Writes db  dictionary to ./.sync/sync
        """
        with open(self.cwd/'.sync/sync', "wb") as f:
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
        directory=os.getcwd()
    ):
        self.cwd=Path(directory)
        logging.basicConfig(level=logging_level)
        self.ftp = FTP("")
        self.ftp.connect(ip, port)
        logging.info("Logging in with {}:{}".format(user, password))
        self.ftp.login(user=user, passwd=password)

    def get_db(self):
        """
            Open sync and store in db (previous)
                If doesn't exist, generate and return
            Overwrite sync with remote sync file 
                Read remote_sync to remote
        """
        # Check for previous db
        if os.path.exists(self.cwd/"./.sync/sync"):
            with open(self.cwd/"./.sync/sync", "rb") as f:
                db = pickle.load(f)
        else:
            # Else generate
            db = self.db = self.generateDB()
        # Get remote db, overwrite local sync file
        self.downloadFile("./.sync/sync")
        with open(self.cwd/"./.sync/sync", "rb") as f:
            remote = pickle.load(f)
        logging.debug("db = {}\nremote = {}".format(db, remote))
        return db, remote

    def deleteFile(self, filename):
        logging.info("Deleting from  remote " + filename)
        self.ftp.delete(filename[2:])  # 2: Is to remove './'

    def uploadFile(self, filename):
        self.ftp.storbinary("STOR " + filename, open(Path(filename), "rb"))
        logging.info("Uploaded " + filename)

    def downloadFile(self, filename):
        # Create directory if doesn't exist
        if not os.path.exists(os.path.dirname(Path(filename))):
            os.makedirs(os.path.dirname(Path(filename)))
        localfile = open(Path(filename), "wb")
        self.ftp.retrbinary("RETR " + filename, localfile.write, 1024)
        localfile.close()
        logging.info("Downloaded " + filename)

    def getTimestamp(self, file_name):
        """
            Get unix timestamp (since epoch) from remote system
            of given file_name
        """
        file_name = file_name[2:]
        x = self.ftp.mlsd("", ["modify"])
        # Since mlsd returns tuple with modify time as UTC, logic to convert it
        for f, mtime in x:
            if f == file_name:
                ts = mtime["modify"]
                time = (
                    datetime.strptime(ts, "%Y%m%d%H%M%S")
                    .replace(tzinfo=timezone.utc)
                    .timestamp()
                )
                return time

    def sync(self):
        prev_db, remote = self.get_db()
        db = self.db = self.generateDB()
        perfect_files = []
        for i in db:
            if prev_db.get(i, False):
                # Check if file has been deleted
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
                if self.getTimestamp(i) > os.stat(Path(i)).st_mtime:
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
        # Refresh DB
        self.dumpDB(self.db)


# Client
if sys.argv[1].lower() == "c":
    c = Client()
    c.sync()
    c.ftp.quit()
# Server
if sys.argv[1].lower() == "s":
    Server().serve_forever()
