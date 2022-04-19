"""
   Copyright (C) Mov.ai  - All Rights Reserved
   Unauthorized copying of this file, via any medium is strictly prohibited
   Proprietary and confidential

   Developers:
   - Manuel Silva (manuel.silva@mov.ai) - 2020
   - Tiago Teixeira (tiago.teixeira@mov.ai) - 2020
"""
import argparse
import json
import os
import sys
import tempfile
import zipfile
from movai_core_shared.logger import Log
from dal.scopes import Package

sys.path.append(os.path.abspath('..'))


def getFolderStructure(folder, fileDict):
    # in order to delete the first '/' on the resource names
    if folder[-1] != '/':
        folder += '/'
    for root, dirs, files in os.walk(folder):
        if not root[-1] == "/":
            new_dir = root + "/"
        else:
            new_dir = root
        #path = root.split(os.sep)
        for file in files:
            filename = new_dir + file
            if not os.path.islink(filename) :
                f_o = open(filename, 'rb')
                fileDict[filename.replace(folder, "")] = f_o.read()
                f_o.close()

def main(build_folder: str, package_name: str):
    logger = Log.get_logger('package.updater.mov.ai')

    build_files = {}

    getFolderStructure(build_folder, build_files)

    try:
        pkg = Package(package_name)
        pkg.remove()
        del pkg
        logger.info("Overwritting Package '%s'" % package_name)
    except:
        logger.info("Creating Package '%s'" % package_name)
    
    pkg = Package(package_name, new=True)

    for x in build_files:
        pkg.add('File', x, Value=build_files[x])
        logger.info("File '%s' added to package '%s'" % (x,package_name))



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Upload UI tool")
    parser.add_argument("-p", "--package", help="package name", type=str)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--folder", help="build folder", type=str)
    group.add_argument("-z", "--zip", help="zip package", type=str)

    args = parser.parse_args()

    if args.zip:
        # unzip it
        tmpdir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(args.zip, 'r') as zip_pkg:
            zip_pkg.extractall(tmpdir.name)
        args.folder = tmpdir.name
    
    if not args.package:
        # look for package name
        try:
            pkg_json = open(os.path.join(args.folder,'package.json'))
            args.package = json.loads(pkg_json.read())['Package']
            pkg_json.close()
        except:
            print("package.json is missing or doesn't have 'Package' field\nEither solve that or supply --package option")
            exit(45)

    main(args.folder, args.package)

    if args.zip:
        tmpdir.cleanup()
