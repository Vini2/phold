#!/usr/bin/env python3

from pathlib import Path

from loguru import logger

from phold.features.predict_3Di import get_embeddings
from phold.features.predict_3Di_finetune import get_embeddings_finetune


def subcommand_predict(
    gb_dict: dict,
    output: Path,
    prefix: str,
    cpu: bool,
    omit_probs: bool,
    model_dir: Path,
    model_name: str,
    batch_size: int,
    finetune: bool,
    finetune_path: Path,
    proteins_flag: bool,
    fasta_flag: bool,
) -> bool:
    """
    Wrapper command for phold predict. Predicts embeddings using ProstT5 encoder + CNN prediction head.

    Args:
        gb_dict (Dict[str, any]): Dictionary containing GenBank records.
        output (str): Output directory path.
        prefix (str): Prefix for output file names.
        cpu (bool): Flag indicating whether to use CPU for prediction.
        omit_probs (bool): Flag indicating whether to omit prediction probabilities from ProstT5.
        model_dir (str): Directory containing the ProstT5 model.
        model_name (str): Name of the ProstT5 model.
        batch_size (int): Batch size for prediction.
        finetune (bool): Flag indicating whether to use fine-tuned model.
        finetune_path (str): Path to the fine-tuned model.
        proteins_flag (bool): True if phold proteins-predict, false otherwise
        fasta_flag (bool): True if pyrodigal-gv was used to predict CDS from FASTA input. False otherwise

    Returns:
        bool: True if prediction succeeds, False otherwise.
    """

    #########
    # make nested dictionary
    #########

    fasta_aa: Path = Path(output) / f"{prefix}_aa.fasta"

    # if proteins, already done and passed as gb_dict
    if proteins_flag is True:
        cds_dict = gb_dict
    else:
        # Create a nested dictionary to store CDS features by contig ID
        cds_dict = {}
        # makes the nested dictionary {contig_id:{cds_id: cds_feature}}
        for record_id, record in gb_dict.items():
            cds_dict[record_id] = {}
            for cds_feature in record.features:
                if cds_feature.type == "CDS":
                    # due to the weird list issue when parsing from genbank file
                    if fasta_flag is False:
                        cds_feature.qualifiers["translation"] = cds_feature.qualifiers[
                            "translation"
                        ][0]
                        cds_dict[record_id][
                            cds_feature.qualifiers["ID"][0]
                        ] = cds_feature
                    else:
                        cds_dict[record_id][cds_feature.qualifiers["ID"]] = cds_feature

    ########
    ## write the AA CDS to file
    ######
    with open(fasta_aa, "w+") as out_f:
        for contig_id, rest in cds_dict.items():
            aa_contig_dict = cds_dict[contig_id]

            for seq_id, cds_feature in aa_contig_dict.items():
                if proteins_flag is True:
                    out_f.write(f">{seq_id}\n")
                else:
                    out_f.write(f">{contig_id}:{seq_id}\n")
                out_f.write(f"{cds_feature.qualifiers['translation']}\n")

    ############
    # prostt5
    ############

    # generates the embeddings using ProstT5 and saves them to file
    fasta_3di: Path = Path(output) / f"{prefix}_3di.fasta"

    if cpu is True:
        half_precision = False
    else:
        half_precision = True

    if omit_probs:
        output_probs = False
    else:
        output_probs = True

    if finetune is True:
        prediction_success = get_embeddings_finetune(
            cds_dict=cds_dict,
            model_dir=model_dir,
            output_3di=fasta_3di,
            max_batch=batch_size,
            finetuned_model_path=finetune_path,
            proteins_flag=proteins_flag,
        )

    else:
        prediction_success = get_embeddings(
            cds_dict,
            output,
            prefix,
            model_dir,
            model_name,
            fasta_3di,
            half_precision=half_precision,
            max_residues=5000,
            max_seq_len=1000,
            max_batch=batch_size,
            cpu=cpu,
            output_probs=output_probs,
            proteins_flag=proteins_flag,
        )

    return prediction_success
