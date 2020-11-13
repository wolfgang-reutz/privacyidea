# Install

in this folder enter these commands in the terminal:

```shell
python3.7 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
git submodule update --init --recursive
```

create / copy customization folder with a `/etc/privacyide/pi.cfg` file - see README.rst for details!

```shell
./pi-manage createdb
./pi-manage create_enckey
./pi-manage db stamp head -d migrations/
./pi-manage create_audit_keys
./pi-manage admin add <username>
```

# Update

when updating the code from upstream, run this command to update all submodules:

`git pull --recurse-submodules`

to update privacy idea:

```shell
source venv/bin/activate
pip install -r requirements.txt
./pi-manage db upgrade
./pi-manage runserver
```
