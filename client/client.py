from ftplib import FTP
import os
from datetime import datetime, timezone
from hashlib import sha1
import pickle
import logging

logging.basicConfig(level=logging.INFO)
ftp = FTP("")
ftp.connect("localhost", 9090)
logging.info("Logging in with {}:{}".format("user", "12345"))
ftp.login(user="user", passwd="12345")


"""
    TODO:
    1) Configuration for 1-way or 2-way sync,
        1-way: Disable uploads
"""


def generateDB(dir="."):
    """
        Creates a dictionary of directory tree(all files) in dir(default=current dir):
        key: Complete file path.
                EG: ./dir1/dir2/file.ext
        value: sha1sum of the respective file
    """
    try:
        os.mkdir("./.sync")
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


def dumpDB(db):
    """
        Writes db  dictionary to ./.sync/sync
    """
    with open("./.sync/sync", "wb") as f:
        pickle.dump(db, f)
    logging.info("Successfully written db")


def deleteFile(filename):
    logging.info("Deleting from  remote " + filename)
    ftp.delete(filename[2:])


def uploadFile(filename):
    ftp.storbinary("STOR " + filename, open(filename, "rb"))
    logging.info("Uploaded " + filename)


def downloadFile(filename):
    if not os.path.exists(os.path.dirname(filename)):
        os.mkdir(os.path.dirname(filename))
    localfile = open(filename, "wb")
    ftp.retrbinary("RETR " + filename, localfile.write, 1024)
    localfile.close()
    logging.info("Downloaded " + filename)


def getTimestamp(file_name):
    """
        Get unix timestamp (since epoch) from remote system
        of given file_name
    """
    file_name = file_name[2:]
    x = ftp.mlsd("", ["modify"])
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


def init():
    """
        Open sync and store in db (previous)
        Overwrite sync with remote sync file 
            Read remote_sync to remote
    """
    if os.path.exists("./.sync"):
        with open("./.sync/sync", "rb") as f:
            db = pickle.load(f)
    else:
        db = generateDB()
    downloadFile("./.sync/sync")
    with open("./.sync/sync", "rb") as f:
        remote = pickle.load(f)
    logging.debug("db = {}\nremote = {}".format(db, remote))
    return db, remote


prev_db, remote = init()
db = generateDB()
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
        uploadFile(i)
    else:
        # SHA1 mismatch. Sync according to newer file
        perfect_files.append(i)
        if getTimestamp(i) > os.stat(i).st_mtime:
            logging.info("Downloading {} since new".format(i))
            downloadFile(i)
        else:
            logging.info("Uploading {} since new".format(i))
            uploadFile(i)

for i in prev_db:
    # Delete files from remote
    deleteFile(i)
    del remote[i]
for i in perfect_files:
    del remote[i]
for i in remote:
    # Download missing files on local
    downloadFile(i)
# Refresh DB
db = generateDB()
dumpDB(db)
ftp.quit()
