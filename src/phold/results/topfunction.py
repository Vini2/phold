#!/usr/bin/env python3
import copy
from pathlib import Path
from typing import Dict, Tuple, Union

import pandas as pd
from loguru import logger


def get_topfunctions(
    result_tsv: Path,
    database: Path,
    database_name: str,
    pdb: bool,
    card_vfdb_evalue: float,
    proteins_flag: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Process Foldseek output to extract top functions and weighted bitscores.

    Args:
        result_tsv (Path): Path to the Foldseek result TSV file.
        database (Path): Path to the database directory.
        database_name (str): Name of the database.
        pdb (bool): Flag indicating whether the PDB format structures have been added.
        card_vfdb_evalue (float): E-value threshold for card and vfdb hits.
        proteins_flag (bool): Flag indicating whether proteins are used.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: A tuple containing two DataFrames:
            1. DataFrame containing the top functions extracted from the Foldseek output.
            2. DataFrame containing weighted bitscores for different functions.
    """

    logger.info("Processing Foldseek output")

    col_list = [
        "query",
        "target",
        "bitscore",
        "fident",
        "evalue",
        "qStart",
        "qEnd",
        "qLen",
        "tStart",
        "tEnd",
        "tLen",
    ]

    foldseek_df = pd.read_csv(
        result_tsv, delimiter="\t", index_col=False, names=col_list
    )

    # gets the cds
    if pdb is False and proteins_flag is False:
        # prostt5
        foldseek_df[["contig_id", "cds_id"]] = foldseek_df["query"].str.split(
            ":", expand=True, n=1
        )
    # pdb or proteins_flag or both
    else:
        foldseek_df["cds_id"] = foldseek_df["query"].str.replace(".pdb", "")

    # clean up later
    if database_name == "all_phold_structures" or database_name == "all_phold_prostt5":
        foldseek_df["target"] = foldseek_df["target"].str.replace(".pdb", "")
        # split the target column as this will have phrog:protein
        foldseek_df[["phrog", "tophit_protein"]] = foldseek_df["target"].str.split(
            ":", expand=True, n=1
        )

    foldseek_df = foldseek_df.drop(columns=["target"])
    foldseek_df["phrog"] = foldseek_df["phrog"].str.replace("phrog_", "")

    mask = foldseek_df["phrog"].str.startswith("envhog_")
    # strip off envhog
    foldseek_df.loc[mask, "phrog"] = foldseek_df.loc[mask, "phrog"].str.replace(
        "envhog_", ""
    )
    # add envhog to protein
    foldseek_df.loc[mask, "tophit_protein"] = (
        "envhog_" + foldseek_df.loc[mask, "tophit_protein"]
    )

    foldseek_df["phrog"] = foldseek_df["phrog"].astype("str")

    # read in the mapping tsv
    phrog_annot_mapping_tsv: Path = Path(database) / "phold_annots.tsv"
    phrog_mapping_df = pd.read_csv(phrog_annot_mapping_tsv, sep="\t")
    phrog_mapping_df["phrog"] = phrog_mapping_df["phrog"].astype("str")

    # join the dfs
    foldseek_df = foldseek_df.merge(phrog_mapping_df, on="phrog", how="left")

    # Replace NaN values in the 'product' column with 'hypothetical protein'
    foldseek_df["product"] = foldseek_df["product"].fillna("hypothetical protein")

    # filter out rows of foldseek_df where vfdb or card - stricter threshold due to Enault et al
    # https://www.nature.com/articles/ismej201690
    # defaults to 1e-10
    foldseek_df = foldseek_df[
        ((foldseek_df["phrog"] == "vfdb") | (foldseek_df["phrog"] == "card"))
        & (foldseek_df["evalue"].astype(float) < float(card_vfdb_evalue))
        | ((foldseek_df["phrog"] != "vfdb") & (foldseek_df["phrog"] != "card"))
    ]

    def custom_nsmallest(group):
        # where all the
        if all(group["product"] == "hypothetical protein"):
            min_row_index = group["evalue"].idxmin()
            # Get the entire row
            return group.loc[min_row_index]
        else:
            group = group[group["product"] != "hypothetical protein"]
            min_row_index = group["evalue"].idxmin()
            # Get the entire row
            return group.loc[min_row_index]

    topfunction_df = (
        foldseek_df.groupby("query", group_keys=True)
        .apply(custom_nsmallest)
        .reset_index(drop=True)
    )

    topfunction_dict = dict(zip(topfunction_df["query"], topfunction_df["function"]))

    # Remove the original 'query' column
    topfunction_df = topfunction_df.drop(columns=["query"])

    # scientific notation to 3dp
    topfunction_df["evalue"] = topfunction_df["evalue"].apply(
        lambda x: "{:.3e}".format(float(x))
    )

    def weighted_function(group: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate weighted function proportion based on bitscores.

        Args:
            group (pd.DataFrame): DataFrame containing foldseek search results for a group.

        Returns:
            pd.DataFrame: DataFrame containing weighted function proportion.
        """

        # normalise counts by total bitscore
        weighted_counts_normalised = {}
        # total_bitscore = group['bitscore'].sum()
        bitscore_by_function = group.groupby("function")["bitscore"].sum().to_dict()

        total_functional_bitscore = group[group["function"] != "unknown function"][
            "bitscore"
        ].sum()

        if total_functional_bitscore == 0:
            top_bitscore_function = "unknown function"
            top_bitscore_perc = 0

        # everything except unknown function
        # get total bitscore of the hits with function
        else:
            # get the weighted bitscore
            for key, value in bitscore_by_function.items():
                if key != "unknown function":
                    weighted_counts_normalised[key] = round(
                        value / total_functional_bitscore, 3
                    )

            top_bitscore_function = max(
                weighted_counts_normalised, key=weighted_counts_normalised.get
            )
            top_bitscore_perc = max(weighted_counts_normalised.values())

        d = {
            "function_with_highest_bitscore_proportion": [top_bitscore_function],
            "top_bitscore_proportion_not_unknown": [top_bitscore_perc],
            "head_and_packaging_bitscore_proportion": [
                weighted_counts_normalised.get("head and packaging", 0)
            ],
            "integration_and_excision_bitscore_proportion": [
                weighted_counts_normalised.get("integration and excision", 0)
            ],
            "tail_bitscore_proportion": [weighted_counts_normalised.get("tail", 0)],
            "moron_auxiliary_metabolic_gene_and_host_takeover_bitscore_proportion": [
                weighted_counts_normalised.get(
                    "moron, auxiliary metabolic gene and host takeover", 0
                )
            ],
            "DNA_RNA_and_nucleotide_metabolism_bitscore_proportion": [
                weighted_counts_normalised.get("DNA, RNA and nucleotide metabolism", 0)
            ],
            "connector_bitscore_proportion": [
                weighted_counts_normalised.get("connector", 0)
            ],
            "transcription_regulation_bitscore_proportion": [
                weighted_counts_normalised.get("transcription regulation", 0)
            ],
            "lysis_bitscore_proportion": [weighted_counts_normalised.get("lysis", 0)],
            "other_bitscore_proportion": [weighted_counts_normalised.get("other", 0)],
            "unknown_function_bitscore_proportion": [
                weighted_counts_normalised.get("unknown function", 0)
            ],
        }

        weighted_bitscore_df = pd.DataFrame(data=d)

        return weighted_bitscore_df

    weighted_bitscore_df = foldseek_df.groupby("query", group_keys=True).apply(
        weighted_function
    )

    weighted_bitscore_df.reset_index(inplace=True)
    weighted_bitscore_df["query"] = weighted_bitscore_df["query"].str.replace(
        ".pdb", ""
    )
    weighted_bitscore_df = weighted_bitscore_df.drop(columns=["level_1"])

    return topfunction_df, weighted_bitscore_df


def calculate_topfunctions_results(
    filtered_tophits_df: pd.DataFrame,
    cds_dict: Dict[str, Dict[str, dict]],
    output: Path,
    pdb: bool,
    proteins_flag: bool,
    fasta_flag: bool,
) -> Union[Dict[str, Dict[str, dict]], pd.DataFrame]:
    """
    Calculate top function results based on filtered top hits DataFrame and update CDS dictionary accordingly.

    Args:
        filtered_tophits_df (pd.DataFrame): DataFrame containing filtered top hits.
        cds_dict (Dict[str, Dict[str, dict]]): Dictionary containing CDS information.
        output (Path): Output path.
        pdb (bool): Indicates whether the input is in PDB format.
        proteins_flag (bool): Indicates whether the input is proteins.
        fasta_flag (bool): Indicates whether the input is in FASTA format.

    Returns:
        Union[Dict[str, Dict[str, dict]], pd.DataFrame]: Updated CDS dictionary and/or filtered top hits DataFrame.
    """

    # dictionary to hold the results
    result_dict = {}

    # so I can match with the df row below
    cds_record_dict = {}

    for record_id, cds_entries in cds_dict.items():
        result_dict[record_id] = {}
        for cds_id, cds_info in cds_entries.items():
            result_dict[record_id][cds_id] = {}
            cds_record_dict[cds_id] = record_id

    # Get record_id for every cds_id and merge into the df
    if pdb is True:
        cds_record_df = pd.DataFrame(
            list(cds_record_dict.items()), columns=["cds_id", "contig_id"]
        )
        filtered_tophits_df = pd.merge(
            filtered_tophits_df, cds_record_df, on="cds_id", how="left"
        )

    if proteins_flag is True:
        column_order = ["cds_id"] + [
            col for col in filtered_tophits_df.columns if col != "cds_id"
        ]

    else:
        # Move "contig_id" and 'cds_id' to the front of the df
        column_order = ["contig_id", "cds_id"] + [
            col
            for col in filtered_tophits_df.columns
            if col != "contig_id" and col != "cds_id"
        ]
        filtered_tophits_df = filtered_tophits_df[column_order]

    # loop over all the foldseek tophits and add to the dict
    for _, row in filtered_tophits_df.iterrows():
        if proteins_flag is False:
            record_id = row["contig_id"]
        else:
            record_id = "proteins"

        cds_id = row["cds_id"]
        values_dict = {
            "phrog": row["phrog"],
            "product": row["product"],
            "function": row["function"],
            "tophit_protein": row["tophit_protein"],
            "bitscore": row["bitscore"],
            "fident": row["fident"],
            "evalue": row["evalue"],
            "qStart": row["qStart"],
            "qEnd": row["qEnd"],
            "qLen": row["qLen"],
            "tStart": row["tStart"],
            "tEnd": row["tEnd"],
            "tLen": row["tLen"],
        }
        result_dict[record_id][cds_id] = values_dict

    # copy initial cds_dict
    updated_cds_dict = copy.deepcopy(cds_dict)

    phrog_function_mapping = {
        "unknown function": "unknown function",
        "transcription regulation": "transcription regulation",
        "tail": "tail",
        "other": "other",
        "moron, auxiliary metabolic gene and host takeover": "moron, auxiliary metabolic gene and host takeover",
        "lysis": "lysis",
        "integration and excision": "integration and excision",
        "head and packaging": "head and packaging",
        "DNA, RNA and nucleotide metabolism": "DNA, RNA and nucleotide metabolism",
        "connector": "connector",
    }

    # iterates over the records
    for record_id, record in updated_cds_dict.items():
        # iterates over the features
        for cds_id, cds_feature in updated_cds_dict[record_id].items():
            # proteins/FASTA input -> no pharokka input -> fake input to make the updating work
            if proteins_flag is True or fasta_flag is True:
                cds_feature.qualifiers["function"] = ["unknown function"]
                cds_feature.qualifiers["phrog"] = ["No_PHROG"]
                cds_feature.qualifiers["product"] = ["hypothetical protein"]

            # original pharokka phrog categories
            pharokka_phrog_function_category = phrog_function_mapping.get(
                cds_feature.qualifiers["function"][0], None
            )

            # if the result_dict is not empty
            # this is a foldseek hit
            if result_dict[record_id][cds_id] != {}:
                # get the foldseek function
                # function will be None if there is no foldseek hit - shouldn't happen here but error handling
                foldseek_phrog = result_dict[record_id][cds_id].get("phrog", None)

                # same phrog as pharokka do nothing
                # different phrog as pharokka
                if foldseek_phrog != cds_feature.qualifiers["phrog"][0]:
                    # where there was no phrog in pharokka
                    if cds_feature.qualifiers["phrog"][0] == "No_PHROG":
                        updated_cds_dict[record_id][cds_id].qualifiers["phrog"][
                            0
                        ] = result_dict[record_id][cds_id]["phrog"]
                        updated_cds_dict[record_id][cds_id].qualifiers["product"][
                            0
                        ] = result_dict[record_id][cds_id]["product"]
                        updated_cds_dict[record_id][cds_id].qualifiers["function"][
                            0
                        ] = result_dict[record_id][cds_id]["function"]

                    # pharokka has a phrog
                    else:
                        # if the foldseek result is not unknown function then update
                        if (
                            result_dict[record_id][cds_id]["function"]
                            != "unknown function"
                        ):
                            # update
                            updated_cds_dict[record_id][cds_id].qualifiers["phrog"][
                                0
                            ] = result_dict[record_id][cds_id]["phrog"]
                            updated_cds_dict[record_id][cds_id].qualifiers["product"][
                                0
                            ] = result_dict[record_id][cds_id]["product"]
                            updated_cds_dict[record_id][cds_id].qualifiers["function"][
                                0
                            ] = result_dict[record_id][cds_id]["function"]
                        # if foldseek result has unknown function
                        else:
                            # if pharokka has known function
                            # keep the pharokka phrogs - aka do nothing
                            #
                            # if the pharokka has unknown function, update with foldseek hit
                            if (
                                cds_feature.qualifiers["function"][0]
                                == "unknown function"
                            ):
                                updated_cds_dict[record_id][cds_id].qualifiers["phrog"][
                                    0
                                ] = result_dict[record_id][cds_id]["phrog"]
                                updated_cds_dict[record_id][cds_id].qualifiers[
                                    "product"
                                ][0] = result_dict[record_id][cds_id]["product"]
                                updated_cds_dict[record_id][cds_id].qualifiers[
                                    "function"
                                ][0] = result_dict[record_id][cds_id]["function"]

            # no foldseek hits - empty dict
            # will be empty in results dict
            # therefore just leave whatever pharokka has

    return updated_cds_dict, filtered_tophits_df


def initialize_function_counts_dict(
    record_id: str, count_dict: Dict[str, int], cds_count: int
) -> Dict[str, int]:
    """
    Initialize function counts dictionary for a given record ID.

    Args:
        record_id (str): ID of the record.
        count_dict (Dict[str, int]): Dictionary containing function counts.
        cds_count (int): Count of CDS.

    Returns:
        Dict[str, int]: Updated function counts dictionary.
    """
    count_dict[record_id]["cds_count"] = cds_count
    count_dict[record_id].update(
        {
            "phrog_count": 0,
            "connector": 0,
            "DNA, RNA and nucleotide metabolism": 0,
            "head and packaging": 0,
            "integration and excision": 0,
            "lysis": 0,
            "moron, auxiliary metabolic gene and host takeover": 0,
            "other": 0,
            "tail": 0,
            "transcription regulation": 0,
            "unknown function": 0,
        }
    )

    return count_dict
