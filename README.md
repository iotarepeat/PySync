# Pysync
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.6](https://img.shields.io/badge/python-3.6-blue.svg)](https://www.python.org/downloads/release/python-360/)


Sync two or more directories on same network
## Requirments
Install Python 3.x

[Link](https://www.python.org/downloads/)

Before running server from main.py
,like this.
 ```console
python main.py s
```
or
 ```console
python3 main.py s
```
Install pyftplib Module
```console
pip install pyftplib
```


## Usage
1. Run setup.py to setup the ___Server mode___ or to Setup the ___Client mode___
2. If ***Server*** is selected by entering **'1'** in command Line, Enter the absolute path ie **If the path is built starting from the system root, it is called absolute.**
3. Select Read only Mode to be enable or disable ie **Enter in command line 'y' for Read Only mode and Enter 'n' for it to be disabled**  
***Read Only: In this case, read-only means that the file can be only opened or read; you cannot delete, change, or rename any file that's been flagged read-only.***
4. Make sure the **Client** is running by 
```console
python main.py c
```
5. A list of available IP's would be shown
6. Follow the instructions in Command Line Prompt
7. To **ONLY** run **Client** Followed by the prompt to Enter Folder path to where you want to sync
```console
python setup.py
>python setup.py
1) Server
2) Client
>> 2
Client is running

```
Make sure the server is running 
```console
python main.py s
[I 2019-03-21 22:15:29] >>> starting FTP server on 0.0.0.0:9090, pid=22424 <<<
[I 2019-03-21 22:15:29] concurrency model: multi-thread
[I 2019-03-21 22:15:29] masquerade (NAT) address: None
[I 2019-03-21 22:15:29] passive ports: None

```
## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
[GNU GPLv3](https://choosealicense.com/licenses/gpl-3.0/)
