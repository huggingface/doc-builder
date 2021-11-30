import yaml
from packaging import version as package_version

def update_versions_file(build_path, version):
    """
    Insert new version into versions.yml file of the library
    Assumes that versions.yml exists and has its first entry as master version
    """
    if version == "master":
        return
    with open(f'{build_path}/versions.yml', "r") as versions_file:
        versions = yaml.load(versions_file, yaml.FullLoader)
    
        if versions[0]["version"] != "master":
            raise ValueError(f'{build_path}/versions.yml does not contain master version')
        
        master_version, sem_versions = versions[0], versions[1:]
        new_version = {'version': version}
        did_insert = False
        for i, value in enumerate(sem_versions):
            if package_version.parse(new_version['version']) > package_version.parse(value['version']):
                sem_versions.insert(i, new_version)
                did_insert = True
                break
        if not did_insert:
            sem_versions.append(new_version)

    with open(f'{build_path}/versions.yml', "w") as versions_file:
        versions_updated = [master_version] + sem_versions
        yaml.dump(versions_updated, versions_file)
