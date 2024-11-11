Linux VM Management

This script is intended to help set up and run virtual lab environments on Linux systems. The intended use case is for the educator to set this up on their own system, then have students SSH in as low-privileged users. Either can create and install a lab or a VM with a single command, using either an ISO file or an existing qcow2 image.

Labs are collections of VMs, each with relevant configuration files. When "lab start <category> <lab>" is executed, the lab's VMs are copied to a temporary directory and the copies are started. When ready, the script SSHs into them and transfers the bundled files and executables to the VM, executing the executables.

Exercises are temporary copies of running labs.

Categories are directories, used only for organization.

VMs are the actual virtual machines. Each lives in the "labs/<category>/<lab>/vms/<vm>" directory, and contains:
* A README.txt file. The first line is the description visible when running "lab info"; all of it will be appended to the lab's README.txt and transferred to the VM if you chose.
* A details.yaml file that holds configuration information. Most of this is autogenerated when the VM is created, but you will need to choose what is visible to the user and enter the credentials
* A qcow2 image
* Directories for files to upload and scripts to execute. Note that root scripts require SSH to be configured on the VM to allow logging in as root

All the backend work is done with qemu. You'll need qemu, kvm, virt-install, virt-manager, libvirtd, python3-paramiko, and python3-scp installed.

For first-time setup, run "sudo python3 lab.py create_lab <category> <lab_name> --first-time". This won't install the dependencies, but will copy the script to your /bin directory, create a "/bin/lab.sh" wrapper for it to aid with passwordless sudo compatibility*, and creates an alias in your .bashrc (alias lab='sudo /bin/lab.sh'). It does create the lab's template as well.

I recommend creating a dedicated "vms" group and adding all relevant users to it, then adding the following line to /etc/sudoers:
%vms ALL= NOPASSWD: /bin/lab.sh
In combination with the alias, this allows you to run and manage the labs without entering sudo/the sudo password each time. The alias and bash wrapper are needed to avoid weirdness with sudo: specifying "/usr/bin/python3 <script>" in your sudoers file means that you'll need separate lines for each possible command-line argument, which, when the arguments include user-generated lab names, is obviously undesirable. Trying to get around that with a python3 shebang and executing the script directly also doesn't work: it gets translated to "/usr/bin/python3 <script>" before it makes it to the sudoers file, and now you can't even execute the script without arguments.

For the moment, this is a slapdash project thrown together over the course of a long weekend. Expect bugs.
