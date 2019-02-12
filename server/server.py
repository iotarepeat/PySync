from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from hashlib import sha1
import os, pickle

"""
    TODO:
    1) Write logic for deleted files
    2) Create threads for sha1 as big files will take time
    3) Use threaded FTPServer 
    4) Write logic to create unique folder mappings eg
        dir2 = canjsk
        dir2/dir2 = ckamskm
        dir2/dir1 = safnj
        Which will be used as userID 
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
    return db


def dumpDB(db):
    """
        Writes db  dictionary to ./.sync/sync
    """
    with open("./.sync/sync", "wb") as f:
        pickle.dump(db, f)


genAndDump = lambda x: dumpDB(
    generateDB()
)  # Utility function to refresh db on closed connection
if not os.path.exists('./.sync'):
    genAndDump(1)

authorizer = DummyAuthorizer()
# TODO: Replace with unique username,password for unique homedirs
authorizer.add_user("user", "12345", homedir=os.getcwd(), perm="elradfmw")

handler = FTPHandler
handler.authorizer = authorizer
handler.on_disconnect = genAndDump # Refresh DB on close

server = FTPServer(("127.0.0.1", 9090), handler)
server.serve_forever()
