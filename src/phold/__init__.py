#!/usr/bin/env python3
"""phold"""

import os
import shutil
from pathlib import Path

import click
from loguru import logger

from phold.io.handle_genbank import get_genbank

from phold.utils.util import (
    begin_phold,
    end_phold,
    get_version,
    print_citation
)

from phold.features.predict_3Di import get_embeddings

from phold.features.create_foldseek_db import  generate_foldseek_db_from_aa_3di

from phold.utils.validation import instantiate_dirs

from phold.features.run_foldseek import run_foldseek_search, create_result_tsv

# from phold.utils.validation import (
#     check_evalue,
#     instantiate_dirs,
#     validate_choice_autocomplete,
#     validate_choice_mode,
#     validate_custom_db_fasta,
#     validate_fasta,
#     validate_fasta_all,
#     validate_fasta_bulk,
#     validate_ignore_file,
# )


log_fmt = (
    "[<green>{time:YYYY-MM-DD HH:mm:ss}</green>] <level>{level: <8}</level> | "
    "<level>{message}</level>"
)


def common_options(func):
    """Common command line args
    Define common command line args here, and include them with the @common_options decorator below.
    """
    options = [
        click.option(
            "-i",
            "--input",
            help="Path to input file in Genbank format",
            type=click.Path(),
            required=True,
        ),
        click.option(
            "-o",
            "--output",
            default="output_phold",
            show_default=True,
            type=click.Path(),
            help="Output directory ",
        ),
        click.option(
            "-t",
            "--threads",
            help="Number of threads to use with Foldseek",
            default=1,
            type=int,
            show_default=True,
        ),
        click.option(
            "-p",
            "--prefix",
            default="phold",
            help="Prefix for output files",
            type=str,
            show_default=True,
        ),
        click.option(
            "-f",
            "--force",
            is_flag=True,
            help="Force overwrites the output directory",
        ),
        click.option(
            "-m",
            "--model",
            required=False,
            type=str,
            default="Rostlab/ProstT5_fp16",
            help='Either a path to a directory holding the checkpoint for a pre-trained model or a huggingface repository link.' 
        ),
        click.option(
            "-d",
            "--database",
            required=True,
            type=click.Path(),
            help='Path to foldseek PHROGs database.' 
        )
    ]
    for option in reversed(options):
        func = option(func)
    return func


@click.group()
@click.help_option("--help", "-h")
@click.version_option(get_version(), "--version", "-V")
def main_cli():
    1 + 1


"""
Chromosome command
"""


@main_cli.command()
@click.help_option("--help", "-h")
@click.version_option(get_version(), "--version", "-V")
@click.pass_context
@common_options
@click.option(
    "-e",
    "--evalue",
    default="1e-3",
    help="e value threshold for Foldseek",
    show_default=True,
)
def run(
    ctx,
    input,
    output,
    threads,
    prefix,
    evalue,
    force,
    model,
    database,
    **kwargs,
):
    """Runs phold"""

    # validates the directory  (need to before I start phold or else no log file is written)
    instantiate_dirs(output, force)

    output: Path = Path(output)
    logdir: Path = Path(output) / "logs"

    params = {
        "--input": input,
        "--output": output,
        "--threads": threads,
        "--force": force,
        "--prefix": prefix,
        "--evalue": evalue
    }


    # initial logging etc
    start_time = begin_phold(params)

    # validates fasta
    gb_dict = get_genbank(input)
    if not gb_dict:
        logger.warning("Error: no sequences found in genbank file")
        logger.error("No sequences found in genbank file. Nothing to annotate")

    # for key, value in gb_dict.items():
    #     logger.info(f"Parameter: {key} {value}.")

    # Create a nested dictionary to store CDS features by contig ID
    cds_dict = {}

    fasta_aa: Path = Path(output) / "outputaa.fasta"

    # makes the nested dictionary {contig_id:{cds_id: cds_feature}}
    
    for record_id, record in gb_dict.items():
        
        cds_dict[record_id] = {}

        for cds_feature in record.features:
            if cds_feature.type == 'CDS':
                cds_dict[record_id][cds_feature.qualifiers['ID'][0]] = cds_feature

    ## write the CDS to file

    with open(fasta_aa, 'w+') as out_f:
        for contig_id, rest in cds_dict.items():

            aa_contig_dict = cds_dict[contig_id]

            # writes the CDS to file
            for seq_id, cds_feature in aa_contig_dict.items():
                out_f.write(f">{contig_id}:{seq_id}\n")
                out_f.write(f"{cds_feature.qualifiers['translation'][0]}\n")

    ############
    # prostt5
    ############

    # generates the embeddings using ProstT5 and saves them to file
    fasta_3di: Path = Path(output) / "output3di.fasta"
    get_embeddings( cds_dict, output, model,  half_precision=True,    
                   max_residues=3000, max_seq_len=1000, max_batch=100 ) 
    
    ############
    # create foldseek db
    ############

    foldseek_query_db_path: Path = Path(output) / "foldseek_db"
    foldseek_query_db_path.mkdir(parents=True, exist_ok=True)

    generate_foldseek_db_from_aa_3di(fasta_aa, fasta_3di, foldseek_query_db_path, logdir, prefix )

    ###########
    # run foldseek search
    ###########

    short_db_name = f"{prefix}_foldseek_database"
    query_db: Path = Path(foldseek_query_db_path) / short_db_name
    target_db: Path = Path(database) / "toy_prophage_db"

    # make result and temp dirs 
    result_db: Path = Path(output) / "result_db"
    result_db.mkdir(parents=True, exist_ok=True)
    temp_db: Path = Path(output) / "temp_db"
    temp_db.mkdir(parents=True, exist_ok=True)

    # run foldseek search
    run_foldseek_search(query_db, target_db,result_db, temp_db, threads, logdir )

    # make result tsv 
    result_tsv: Path =  Path(output) / "foldseek_results.tsv"
    create_result_tsv(query_db, target_db, result_db, result_tsv, logdir)




    # validates fasta
    #validate_fasta(input)

    # validate e value
    #check_evalue(evalue)



    # end phold
    end_phold(start_time)


@click.command()
def citation(**kwargs):
    """Print the citation(s) for this tool"""
    print_citation()


# main_cli.add_command(run)
main_cli.add_command(citation)


def main():
    main_cli()


if __name__ == "__main__":
    main()