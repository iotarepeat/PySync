# Pysync
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-360/)


Sync two or more directories on same network
## Requirments
Install Python 3.x

[Link](https://www.python.org/downloads/)

Install pyftplib Module if you intend to run a server on that machine.
```console
pip install pyftplib
```


## Initial setup
**Note: setup.py would suffice for most home networks. For other networking setups, please modify the server.json and client.json**
1. Run setup.py to setup the ___Server mode___ or to Setup the ___Client mode___
2. If ***Server*** is selected by entering **'1'** in command Line, Enter the absolute path ie **If the path is built starting from the system root, it is called absolute.**
3. Select Read only Mode to be enable or disable ie **Enter in command line 'y' for Read Only mode and Enter 'n' for it to be disabled**  
***Read Only: In this case, read-only means that the file can be only opened or read (by client); you cannot delete, change, or rename any file that's been flagged read-only.***
4. Make sure the **Client** is running on other devices.
5. A list of available IP's would be shown
6. Follow the instructions in Command Line Prompt
7. Sharing ip would create a [mesh topology](https://en.wikipedia.org/wiki/Mesh_networking), else [star topology](https://en.wikipedia.org/wiki/Star_network).
8. To **ONLY** run **Client** Followed by the prompt to Enter Folder path to where you want to sync
```console
python setup.py
>python setup.py
1) Server
2) Client
>> 2
Client is running

```
## Setup is done.

## To run server
```console
python main.py s
[I 2019-03-21 22:15:29] >>> starting FTP server on 0.0.0.0:9090, pid=22424 <<<
[I 2019-03-21 22:15:29] concurrency model: multi-thread
[I 2019-03-21 22:15:29] masquerade (NAT) address: None
[I 2019-03-21 22:15:29] passive ports: None

```
## To run client
```console
python main.py c
```
# Note: You will need to run main.py (s|c) on regular intervals.
1. Windows: Use task schedular
2. Linux: Use crontab
## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
[GNU GPLv3](https://choosealicense.com/licenses/gpl-3.0/)
