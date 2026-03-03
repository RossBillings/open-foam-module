Here are the essential Multipass commands for your OpenFOAM workflow:

## VM Management
```bash
multipass list                          # see all VMs and their status
multipass start openfoam                # start the VM
multipass stop openfoam                 # stop the VM
multipass shell openfoam                # SSH into the VM
multipass info openfoam                 # CPU, memory, disk usage
```

## Running Commands Without Entering the VM
```bash
multipass exec openfoam -- foamVersion
multipass exec openfoam -- bash -c "source /opt/openfoam13/etc/bashrc && foamRun"
```
The `bash -c` form is important — single commands work without it, but anything needing the OF environment requires sourcing bashrc first.

## File Transfer
```bash
# Copy file from VM to Mac
multipass transfer openfoam:/home/ubuntu/OpenFOAM/ubuntu-13/run/cavity/cavity.foam ~/Desktop/

# Copy directory recursively from VM to Mac
multipass transfer -r openfoam:/home/ubuntu/OpenFOAM/ubuntu-13/run/cavity ~/Desktop/cavity

# Copy file from Mac to VM
multipass transfer ~/Desktop/myfile.txt openfoam:/home/ubuntu/
```

## Mounts (persistent shared folder)
```bash
# Mount a Mac folder into the VM
multipass mount ~/Desktop/foam-shared openfoam:/home/ubuntu/shared

# Check active mounts
multipass info openfoam

# Unmount
multipass umount openfoam:/home/ubuntu/shared
```
A persistent mount is worth setting up — it eliminates the transfer step entirely and lets ParaView read results directly from the mounted path.

## Snapshots (useful before risky changes)
```bash
multipass snapshot openfoam --name before-integration
multipass restore openfoam --snapshot before-integration
multipass list --snapshots
```

## Resource Management
```bash
# You can't resize a running VM — stop first
multipass stop openfoam
multipass set local.openfoam.cpus=4
multipass set local.openfoam.memory=8G
multipass set local.openfoam.disk=20G
multipass start openfoam
```
Relevant for parallel runs when you get to decomposePar — more CPUs available in the VM means faster solves.

---

The mount approach is the most useful for your workflow — want me to walk through setting that up so ParaView reads directly from the VM without manual transfers?