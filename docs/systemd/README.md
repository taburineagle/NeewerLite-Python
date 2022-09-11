# Install NeewerLite-Python as a systemd service on Linux

***The following instructions were executed on Raspberry Pi OS 64-bit bullseye as the default user (pi).***

In order to enable the application as a service on a Linux systemd enabled system, you need to follow these steps: 

## Prepare the environment

1. Install the initial dependencies to run the application on your system.

    ```bash
    sudo apt install git unzip python3 python3-pip
    ```

2. Install [bleak](https://pypi.org/project/bleak/) in your environment.

    ```bash
    pip3 install bleak
    ```

3. Download the latest release of NeewerLite-Python and export it the folder `/opt/NeewerLite-Python/` . 

    ```bash
    wget https://github.com/taburineagle/NeewerLite-Python/archive/refs/tags/0.12b.zip -O ~/NeewerLite-Python.zip && sudo unzip ~/NeewerLite-Python.zip -d /opt/
    ```

4. Rename the folder that was created to `NeewerLite-Python`. 

    ```bash
    sudo mv /opt/NeewerLite-Python-0.12b /opt/NeewerLite-Python
    ```

5. Change the ownership of the files in the folder to the executing user. 

    ```bash
    sudo chown pi:pi /opt/NeewerLite-Python/*
    ```

6. Enable the execution bit of the python files.

    ```bash
    chmod +x /opt/NeewerLite-Python/*.py
    ```

7. Test the execution of the application by running the following command then by hitting CTRL+C to stop the test.  

    ```bash
    python3 /opt/NeewerLite-Python/NeewerLite-Python.py --http
    ```
    
## If you have issues linking to lights using NeewerLite-Python, take these steps

1. Add the executing user to the bluetooth group.

    ```bash
    sudo usermod -G bluetooth -a pi
    ```

2. Confirm that the user has been added to the group.

    ```bash
    cat /etc/group | grep bluetooth
    ```  

3. Restart the Pi

    ```bash
    sudo reboot
    ```

4. Again, test the execution of NeewerLite-Python by running the following command then by hitting CTRL+C to stop the test.

    ```bash
    python3 /opt/NeewerLite-Python/NeewerLite-Python.py --http
    ```

## Enable the application as a systemd service

1. Edit the systemd template file `/opt/NeewerLite-Python/docs/systemd/neewerlite-python.service` with the editor of your choice and modify the user and group name if you intend to run the application under another user and group than `pi`. 

2. Copy the file `/opt/NeewerLite-Python/docs/systemd/neewerlite-python.service` to `/etc/systemd/system/` . 

    ```bash
    sudo cp /opt/NeewerLite-Python/docs/systemd/neewerlite-python.service /etc/systemd/system/
    ```

3. Reload systemd manager configuration. 

    ```bash
    sudo systemctl daemon-reload
    ```

4. Enable the application as a service. Note that enabling the service will make the script start as a daemon when the operating system boots up. 

    ```bash
    sudo systemctl enable neewerlite-python.service
    ```

5. Start the service. 

    ```bash
    sudo systemctl start neewerlite-python
    ```

6. Get the service' status

    ```bash
    sudo systemctl status neewerlite-python
    ```
