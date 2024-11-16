#!/usr/bin/env python3

import os, subprocess, argparse, pathlib, shutil, yaml, sys, time, paramiko, datetime
from scp import SCPClient

BASEDIR =           pathlib.Path('/opt/lab')
LABS_DIR =          pathlib.Path(BASEDIR / 'labs')
ACTIVE_DIR =        pathlib.Path(BASEDIR / 'active')
SUSPENDED_DIR =     pathlib.Path(BASEDIR / 'suspended')
SCRIPT_LOCATION =   pathlib.Path('/bin/lab.py')
VMSIZE =            '40G'
VMCPUS =            '4'
VMMEM =             '8192'

class Lab:
    def __init__(self, path):
        self.name = path.name
        self.path = path
        with open(self.path / 'README.txt', 'r') as f:
            self.description = f.readlines()[0]

    def start(self):
        exercise_id = f'{self.path.parent.name}-{self.name}-{datetime.datetime.now().strftime("%d%H%M%S")}'
        print(f'Exercise ID: {exercise_id}')
        exercise = Exercise(exercise_id)
        exercise.start()

    def info(self):
        print(self.description)

class Exercise:
    # Get status from directory
    def __init__(self, id):
        self.id = id
        category = self.id.split('-')[0]
        lab_name = self.id.split('-')[1]
        self.lab_path = LABS_DIR / category / lab_name
        self.path = self.lab_path
        self.stoppable = False
        if self.id in [x.name for x in ACTIVE_DIR.iterdir()]:
            self.path = ACTIVE_DIR / self.id
            self.stoppable = True
        elif self.id in [x.name for x in SUSPENDED_DIR.iterdir()]:
            self.path = SUSPENDED_DIR / self.id

        self.vms = [VM(category, lab_name, id, x.name) for x in (self.lab_path / 'vms').iterdir()]

    def start(self):
        # First start the vms, to let them boot
        for vm in self.vms:
            vm.start()

        # Then set up, once the addresses can be populated
        for vm in self.vms:
            vm.setup()

        print(f'Exercise ID: {self.id}')

    def stop(self):
        for vm in self.vms:
            vm.stop()
        if self.stoppable:
            shutil.rmtree(self.path)

    def suspend(self):
        for vm in self.vms:
            vm.suspend()
        shutil.move(self.path, SUSPENDED_DIR / self.id)

    def resume(self):
        shutil.move(self.path, ACTIVE_DIR / self.id)
        for vm in self.vms:
            vm.resume()

    def info():
        for vm in vms:
            print(vm.name)
            print(f'\t{vm.description}')
            if vm.show_ip: print(f'\tIP: {vm.ip}')
            if vm.show_creds: print(f'\tUsername: {vm.user_username}\n\tPassword: {vm.user_password}')
            if vm.show_root_creds: print(f'Root username: {vm.root_username}\n\tRoot password: {vm.root_password}')

class VM:
    def __init__(self, category, lab_name, id, name):
        self.name = name
        self.lab_path = LABS_DIR / category / lab_name / 'vms' / name
        # running_name is used for virsh management commands
        self.running_path = ACTIVE_DIR / f'{id}'
        self.running_name = f'{id}-{name}'
        self.ip = '-'

    def info(self):
        self.loadDetails()


    def getIP(self):
        ip = '-'
        while '-' in ip and ip != None:
            ip = subprocess.check_output(f'virsh domifaddr --full {self.running_name}'.split()).split()[-1].split(b'/')[0].decode()
            time.sleep(1)
        return ip

    def loadDetails(self):
        with open(self.lab_path / 'details.yaml', 'r') as f:
            creds = yaml.safe_load(f)
        self.description = creds['description']
        self.user_username = creds['user_username']
        self.user_password = creds['user_password']
        self.root_username = creds['root_username']
        self.root_password = creds['root_password']
        self.login_as_root = creds['login_as_root']
        self.show_creds = creds['show_creds']
        self.show_root_creds = creds['show_root_creds']
        self.show_readme = creds['show_readme']
        self.ssh_port = creds['ssh_port']
        self.show_ip = creds['show_ip']
        self.os_variant = creds['os_variant']
        if 'cpus' in creds.keys(): self.cpus = creds['cpus']
        else: self.cpus = VMCPUS
        if 'mem' in creds.keys(): self.mem = creds['mem']
        else: self.mem = VMMEM

    def start(self):
        self.image = self.lab_path / f'{self.name}.qcow2'
        self.files = (self.lab_path / 'files').iterdir()
        self.user_scripts = (self.lab_path / 'user_scripts').iterdir()
        self.root_scripts = (self.lab_path / 'root_scripts').iterdir()

        self.loadDetails()

        self.running_path.mkdir()
        self.running_image = self.running_path / f'{self.running_name}.qcow2'

        os.system(f'qemu-img create -f qcow2 -F qcow2 -b {self.image} {self.running_image}')
        os.system(f'virt-install --name {self.running_name} --vcpus {self.cpus} --memory {self.mem} --os-variant {self.os_variant} --controller=scsi,model=virtio-scsi --disk path={self.running_image},bus=scsi --noautoconsole --import')


    def setup(self):
        self.ip = self.getIP()
        
        socket = paramiko.SSHClient()
        socket.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if self.user_username:
            socket.connect(hostname=self.ip, username=self.user_username, password=self.user_password, port=int(self.ssh_port))
            scpsocket = SCPClient(socket.get_transport())
            for file in self.files:
                scpsocket.put(file, f'/tmp/{file.name}')
            for file in self.user_scripts:
                scpsocket.put(file, f'/tmp/{file.name}')
                socket.exec_command(f'cd /tmp && chmod 755 {file.name} && /tmp/{file.name}')
            
            if self.show_readme:
                shutil.copyfile(self.lab_path.parent.parent / 'README.txt', 'tmp_README.txt')
                with open('tmp_README.txt', 'r') as f:
                    initial_contents = f.read()
                with open('tmp_README.txt', 'w') as f:
                    with open(self.lab_path / 'README.txt', 'r+') as g:
                        g.write(initial_contents + g.read())
                scpsocket.put( 'tmp_README.txt', 'README.txt')
                os.remove('tmp_README.txt')
            scpsocket.close()
            socket.close()

        # log in as root if there's either a root script to run, or there's files to transfer and no user username
        if self.login_as_root and (self.root_scripts or (self.files and not self.user_username)):
            socket.connect(hostname=self.ip, username=self.root_username, password=self.root_password, port=int(self.ssh_port))
            scpsocket = SCPClient(socket.get_transport())
            if not self.user_username:
                for file in self.files:
                    scpsocket.put(file, f'/tmp/{file.name}')
                if self.show_readme: scpsocket.put(self.lab_path.parent.parent / 'README.txt', 'README.txt')
            for file in root_scripts:
                scpsocket.put(file, f'/tmp/{file.name}')
                socket.exec_command(f'cd /tmp && chmod 755 {file.name} && /tmp/{file.name}')
            scpsocket.close()
            socket.close()

        print(f'[*] {self.running_name} started with IP: {self.ip}')
        if self.show_creds:
            print(f'Credentials are {self.user_username} / {self.user_password}\n')
        if self.show_root_creds:
            print(f'Credentials are {self.root_username} / {self.root_password}\n')


    def stop(self):
        os.system(f'virsh destroy {self.running_name}')
        os.system(f'virsh undefine {self.running_name}')

    def suspend(self):
        os.system(f'virsh managedsave {self.running_name}')

    def resume(self):
        os.system(f'virsh start {self.running_name}')
        self.ip = self.getIP()

        print(f'[*] {self.running_name} resumed with IP: {self.ip}')
        if self.show_creds:
            print(f'Credentials are {self.user_username} / {self.user_password}\n')
        if self.show_root_creds:
            print(f'Credentials are {self.root_username} / {self.root_password}\n')

def createLab(category, name):
    (LABS_DIR / category).mkdir(exist_ok=True)

    if checkExistence('lab', name, category) is True:
        error('Lab already exists')
    
    (LABS_DIR / category / name).mkdir()
    
    LABPATH = LABS_DIR / category / name
    (LABPATH / 'vms').mkdir()
    with open(LABPATH / 'README.txt', 'w') as f:
        f.write('In this file, write instructions on what to do in this lab\n\
    The first line should be the description; a quick blurb to describe the function of the lab\n\
    Created VMs go in the "vms" directory\n\
    For each VM, put any files you wish transferred to the VM into its "files" folder. These will be put into the VM\'s "/tmp" directory after it boots.\n\
    Then add any scripts you wish to run into the user or root scripts directory. They will be put into the VM\'s "/tmp" directory after it boots, then automatically executed as the appropriate user\n\
    Remember to put credentials into the VM\'s "details.yaml" file using YAML syntax from the template.\n')

def createVM(category, lab, name, os_variant, size, cpus, memory, existing_qcow2, iso):
    VMPATH = LABS_DIR / category / lab / 'vms' / name
    VMPATH.mkdir()
    with open(VMPATH / 'README.txt', 'w') as f:
        f.write('In this file, write instructions on what to do in this lab\n\
    The first line should be the description; a quick blurb to describe the function of the lab\n\
    Created VMs go in the "vms" directory\n\
    For each VM, put any files you wish transferred in into its "files" folder. These will be put into the VM\'s "/tmp" directory after it boots.\n\
    Then add any scripts you wish to run into the user or root scripts directory. They will be put into the VM\'s "/tmp" directory after it boots, then automatically executed as the appropriate user\n\
    Remember to put credentials into the VM\'s "details.yaml" file using YAML syntax from the template.\n')
    (VMPATH / 'user_scripts').mkdir()
    (VMPATH / 'root_scripts').mkdir()
    (VMPATH / 'files').mkdir()
    with open(VMPATH / 'details.yaml', 'w') as f:
        f.write(f'description: "Write a description here"\nuser_username: <user>\nuser_password: <password>\n# Don\'t show credentials if the user isn\'t supposed to log in directly\nshow_creds: true\nroot_username: root\nroot_password: <password>\nshow_root_creds: false\nlogin_as_root: false\n\nshow_readme: true\n#Don\'t show IP for scanning labs\nshow_ip: true\nssh_port: 22\nos_variant: "{os_variant}"\ncpus: "{cpus}"\nmem: "{memory}"')

    if not existing_qcow2:
        os.system(f'qemu-img create -f qcow2 {VMPATH / name}.qcow2 {size}')
        os.system(f'virt-install --name {name} --vcpus {cpus} --memory {memory} --os-variant {os_variant} --controller=scsi,model=virtio-scsi --disk path={VMPATH / name}.qcow2,bus=scsi --cdrom={iso} --noreboot')
        os.chmod((VMPATH / f'{name}.qcow2'), 0o440)

    else:
        shutil.copyfile(existing_qcow2, f'{VMPATH / name}.qcow2')
        os.system(f'virt-install --name {name} --vcpus {cpus} --memory {memory} --os-variant {os_variant} --controller=scsi,model=virtio-scsi --disk path={existing_qcow2},bus=scsi --import --noautoconsole --noreboot')
        os.chmod((VMPATH / f'{name}.qcow2'), 0o440)

def error(msg):
    print(f'[!] {msg}')
    sys.exit()

def setup():
    BASE_DIR.mkdir(exist_ok=True)
    LABS_DIR.mkdir(exist_ok=True)
    ACTIVE_DIR.mkdir(exist_ok=True)
    SUSPENDED_DIR.mkdir(exist_ok=True)

    try:
        shutil.copyfile(sys.argv[0], '/bin/lab.py')
        with open('/bin/lab.sh', 'w') as f:
            f.write('/usr/bin/env bash\n/bin/lab.py')
        with open('~/.bashrc', 'a') as f:
            fowrite('\nalias lab="sudo /bin/lab.sh"')
    except:
        error('Cannot copy self to /bin. Add to your PATH manually')


def parse_args():
    args = argparse.ArgumentParser(prog='lab')
    sp = args.add_subparsers(required=True, dest='action')

    list_args = sp.add_parser('list')
    list_args.add_argument('type', choices=['categories', 'active', 'suspended'])

    list_labs_args = sp.add_parser('list_labs')
    list_labs_args.add_argument('category')

    info_args = sp.add_parser('info')
    info_args.add_argument('category')
    info_args.add_argument('lab')

    start_args = sp.add_parser('start')
    start_args.add_argument('category')
    start_args.add_argument('lab')
    
    stop_args = sp.add_parser('stop')
    stop_args = stop_args.add_argument('exercise_id')

    suspend_args = sp.add_parser('suspend')
    suspend_args = suspend_args.add_argument('exercise_id')

    resume_args = sp.add_parser('resume')
    resume_args = resume_args.add_argument('exercise_id')
    
    create_lab_args = sp.add_parser('create_lab')
    create_lab_args.add_argument('category')
    create_lab_args.add_argument('name')
    create_lab_args.add_argument('--first-time', action='store_true', help='Add the initial directories and copy self to {SCRIPT_LOCATION}')

    create_vm_args = sp.add_parser('create_vm')
    create_vm_args.add_argument('category')
    create_vm_args.add_argument('lab')
    create_vm_args.add_argument('name')
    create_vm_args.add_argument('-o', '--os_variant', help='See valid choices with "virt-install --os-variant list"', required=True)
    create_vm_args.add_argument('-s', '--size', metavar='vdisk_size', default=VMSIZE)
    create_vm_args.add_argument('-c', '--cpus', default=VMCPUS)
    create_vm_args.add_argument('-m', '--memory', default=VMMEM)
    create_vm_args.add_argument('-e', '--existing-qcow2', help='Use existing disk image. Ignores "-i"')
    create_vm_args.add_argument('-i', '--iso')

    return args.parse_args()

def checkExistence(type, name, category=None):
    if type == 'category':
        options = [x.name for x in LABS_DIR.iterdir()]
    elif type == 'lab':
        options = [x.name for x in (LABS_DIR / category).iterdir()]
    elif type == 'active':
        options = [x.name for x in ACTIVE_DIR.iterdir()]
    elif type == 'suspended':
        return [x.name for x in SUSPENDED_DIR.iterdir()]

    if name in options:
        return True
    else: return options


def main():
    args = parse_args()

    match args.action:
        case 'list':
            match args.type:
                case 'categories': print(" ".join([x.name for x in LABS_DIR.iterdir()]))
                case 'suspended': print(" ".join([x.name for x in SUSPENDED_DIR.iterdir()]))
                case 'active': print(" ".join([x.name for x in ACTIVE_DIR.iterdir()]))
        
        case 'list_labs':
            print(" ".join([x.name for x in (LABS_DIR / args.category).iterdir()]))

        case 'info': 
            Lab(LABS_DIR / args.category / args.lab).info()

        case 'start':
            Lab(LABS_DIR / args.category / args.lab).start()

        case 'stop':
            Exercise(args.exercise_id).stop()

        case 'save':
            Exercise(args.exercise_id).suspend()
            
        case 'resume':
            Exercise(args.exercise_id).resume()

        case 'create_lab':
            if args.first_time: setup()
            createLab(args.category, args.name)

        case 'create_vm':
            createVM(args.category, args.lab, args.name, args.os_variant, args.size, args.cpus, args.memory, args.existing_qcow2, args.iso)

main()
