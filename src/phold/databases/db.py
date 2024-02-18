"""
to tar DBs

GZIP=-9 tar cvzf phold_structure_foldseek_db.tar.gz phold_structure_foldseek_db

"""


import hashlib
import os
import shutil
import tarfile
from pathlib import Path

import requests
from alive_progress import alive_bar
from loguru import logger


# set this if changes
CURRENT_DB_VERSION: str = "0.1.0"

# to hold information about the different DBs
VERSION_DICTIONARY = {
    "0.1.0": {
        "md5": "0014b7a982dbf071f8856a5a29a95e30",
        "major": 0,
        "minor": 1,
        "minorest": 0,
        "db_url": "https://zenodo.org/record/7563578/files/pharokka_v1.2.0_database.tar.gz",
        "dir_name": "phold_structure_foldseek_db",
        "tarball": "phold_structure_foldseek_db.tar.gz"
    }
}

CURRENT_VERSION = "0.1.0"



PHOLD_DB_NAMES = [
    "all_phold_prostt5",
    "all_phold_prostt5.index",
    "all_phold_prostt5.dbtype",
    "all_phold_prostt5_ss",
    "all_phold_prostt5_ss.index",
    "all_phold_prostt5_ss.dbtype",
    "all_phold_prostt5_h",
    "all_phold_prostt5_h.index",
    "all_phold_prostt5_h.dbtype",
    "all_phold_structures",
    "all_phold_structures.index",
    "all_phold_structures.dbtype",
    "all_phold_structures.source",
    "all_phold_structures.lookup",
    "all_phold_structures_ss",
    "all_phold_structures_ss.index",
    "all_phold_structures_ss.dbtype",
    "all_phold_structures_h",
    "all_phold_structures_h.index",
    "all_phold_structures_h.dbtype",
    "all_phold_structures_ca",
    "all_phold_structures_ca.index",
    "all_phold_structures_ca.dbtype",
    "phold_annots.tsv",
    "card_plddt_over_70_metadata.tsv",
    "vfdb_description_output.csv",
    "acrs_plddt_over_70_metadata.tsv",
    "defensefinder_plddt_over_70_metadata.tsv"
]



def install_database(db_dir: Path) -> None:
    """
    Install the Phold database.

    Args:
        db_dir Path: The directory where the database should be installed.
    """

    # check the database is installed
    logger.info(f"Checking Phold database installation in {db_dir}.")
    downloaded_flag = check_db_installation(db_dir)
    if downloaded_flag == True:
        logger.info("All Phold databases files are present")
    else:
        logger.info("Some Phold databases files are missing")

        db_url = VERSION_DICTIONARY[CURRENT_DB_VERSION]["db_url"]
        requiredmd5 = VERSION_DICTIONARY[CURRENT_DB_VERSION]["md5"]

        logger.info(f"Downloading Phold database from {db_url}.")

        tarball = VERSION_DICTIONARY[CURRENT_DB_VERSION][tarball]
        tarball_path = Path(f"{db_dir}/{tarball}")

        download(db_url, tarball_path)

        md5_sum = calc_md5_sum(tarball_path)

        if md5_sum == requiredmd5:
            logger.info(f"Phold database file download OK: {md5_sum}")
        else:
            logger.error(
                f"Error: corrupt database file! MD5 should be '{requiredmd5}' but is '{md5_sum}'"
            )

        logger.info(f"Extracting Phold database tarball: file={tarball_path}, output={db_dir}")
        untar(tarball_path, db_dir)
        tarball_path.unlink()


"""
lots of this code from the marvellous bakta https://github.com/oschwengers/bakta, db.py specifically
"""

def download(db_url: str, tarball_path: Path) -> None:
    """
    Download the database from the given URL.

    Args:
        db_url (str): The URL of the database.
        tarball_path (Path): The path where the downloaded tarball should be saved.
    """
    try:
        with tarball_path.open("wb") as fh_out, requests.get(
            db_url, stream=True
        ) as resp:
            total_length = resp.headers.get("content-length")
            if total_length is not None:  # content length header is set
                total_length = int(total_length)
            with alive_bar(total=total_length, scale="SI") as bar:
                for data in resp.iter_content(chunk_size=1024 * 1024):
                    fh_out.write(data)
                    bar(count=len(data))
    except IOError:
        logger.error(
            f"ERROR: Could not download file from Zenodo! url={db_url}, path={tarball_path}"
        )


def calc_md5_sum(tarball_path: Path, buffer_size: int = 1024 * 1024) -> str:
    """
    Calculate the MD5 checksum of the given file.

    Args:
        tarball_path (Path): The path to the file for which the MD5 checksum needs to be calculated.
        buffer_size (int): The buffer size for reading the file.

    Returns:
        str: The MD5 checksum of the file.
    """

    md5 = hashlib.md5()
    with tarball_path.open("rb") as fh:
        data = fh.read(buffer_size)
        while data:
            md5.update(data)
            data = fh.read(buffer_size)
    return md5.hexdigest()


def untar(tarball_path: Path, output_path: Path) -> None:
    """
    Extract the tarball to the output path.

    Args:
        tarball_path (Path): The path to the tarball file.
        output_path (Path): The path where the contents of the tarball should be extracted.
    """
    try:
        with tarball_path.open("rb") as fh_in, tarfile.open(
            fileobj=fh_in, mode="r:gz"
        ) as tar_file:
            tar_file.extractall(path=str(output_path))

        tarpath = Path(output_path) / VERSION_DICTIONARY[CURRENT_DB_VERSION]["dir_name"]

        # Get a list of all files in the directory
        files_to_move = [
            f for f in tarpath.iterdir() if f.is_file()
        ]

        # Move each file to the destination directory
        for file_name in files_to_move:
            destination_path = output_path / file_name.name
            shutil.move(file_name, destination_path)
        # remove the directory
        remove_directory(tarpath)

    except OSError:
        logger.error(f"Could not extract {tarball_path} to {output_path}")



def check_db_installation(db_dir: Path) -> bool:
    """
    Check if the Phold database is installed.

    Args:
        db_dir (Union[str, Path]): The directory where the database is installed.

    Returns:
        bool: True if all required files are present, False otherwise.
    """
    downloaded_flag = True
    for file_name in PHOLD_DB_NAMES:
        path = Path(db_dir) / file_name
        if not path.is_file():
            logger.warning(f"Phold Database file {path} is missing")
            downloaded_flag = False
            break

    return downloaded_flag
