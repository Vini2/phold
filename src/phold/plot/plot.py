from pathlib import Path
from typing import List, Dict

from loguru import logger
from pycirclize import Circos
from pycirclize.parser import Genbank
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
from Bio import SeqUtils
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature


def create_circos_plot(
    contig_id: str,
    contig_sequence: Seq,
    contig_count: int,
    gb_size_dict: Dict[str, int],
    gb_feature_dict: Dict[str, List[SeqFeature]],
    gbk: Genbank,
    interval: int,
    annotations: float,
    title_size: float,
    plot_title: str,
    truncate: int,
    output: Path,
    dpi: int,
    label_size: int,
    label_hypotheticals: bool,
    remove_other_features_labels: bool,
    label_force_list: List[str],
) -> None:
    """
    Create a Circos plot for a given contig.

    Args:
        contig_id (str): Identifier of the contig.
        contig_sequence (Seq): Nucleotide sequence of the contig.
        contig_count (int): Count of contigs.
        gb_size_dict (Dict[str, int]): Dictionary containing sizes of contigs.
        gb_feature_dict (Dict[str, List[SeqFeature]]): Dictionary containing features of contigs.
        gbk (Genbank): Parser for GenBank files from pycirclize.
        interval (int): Interval for x-axis ticks.
        annotations (int): Number of annotations to plot.
        title_size (float): Font size for the plot title.
        plot_title (str): Title of the plot.
        truncate (int): Number of characters to truncate CDS labels to.
        output (str): Output directory path.
        dpi (int): Dots per inch for the output plot.
        label_size (int): Font size for labels.
        label_hypotheticals (bool): Whether to include hypothetical labels.
        remove_other_features_labels (bool): Whether to remove labels for other features.
        label_force_list (List[str]): List of feature IDs to force label.

    Returns:
        None
    """

    png_plot_file: Path = Path(output) / f"{contig_id}.png"
    svg_plot_file: Path = Path(output) / f"{contig_id}.svg"

    # instantiate circos
    seq_len = gb_size_dict[contig_id]
    circos = Circos(sectors={contig_id: seq_len})

    if contig_count == 1:
        circos.text(plot_title, size=int(title_size), r=190)
    else:
        circos.text(contig_id, size=int(title_size), r=190)

    sector = circos.get_sector(contig_id)
    cds_track = sector.add_track((70, 80))
    cds_track.axis(fc="#EEEEEE", ec="none")

    data_dict = {
        "acr_defense_vfdb_card": {"col": "#FF0000", "fwd_list": [], "rev_list": []},
        "unk": {"col": "#AAAAAA", "fwd_list": [], "rev_list": []},
        "other": {"col": "#4deeea", "fwd_list": [], "rev_list": []},
        "tail": {"col": "#74ee15", "fwd_list": [], "rev_list": []},
        "transcription": {"col": "#ffe700", "fwd_list": [], "rev_list": []},
        "dna": {"col": "#f000ff", "fwd_list": [], "rev_list": []},
        "lysis": {"col": "#001eff", "fwd_list": [], "rev_list": []},
        "moron": {"col": "#8900ff", "fwd_list": [], "rev_list": []},
        "int": {"col": "#E0B0FF", "fwd_list": [], "rev_list": []},
        "head": {"col": "#ff008d", "fwd_list": [], "rev_list": []},
        "con": {"col": "#5A5A5A", "fwd_list": [], "rev_list": []},
    }

    fwd_features = [
        feature
        for feature in gb_feature_dict[contig_id]
        if feature.location.strand == 1
    ]
    rev_features = [
        feature
        for feature in gb_feature_dict[contig_id]
        if feature.location.strand == -1
    ]
    cds_features = [
        feature for feature in gb_feature_dict[contig_id] if feature.type == "CDS"
    ]
    trna_features = [
        feature for feature in gb_feature_dict[contig_id] if feature.type == "tRNA"
    ]
    tmrna_features = [
        feature for feature in gb_feature_dict[contig_id] if feature.type == "tmRNA"
    ]
    crispr_features = [
        feature
        for feature in gb_feature_dict[contig_id]
        if feature.type == "repeat_region"
    ]

    # fwd features first

    for f in fwd_features:
        if f.type == "CDS":
            if (
                "vfdb" in f.qualifiers.get("phrog")[0]
                or "card" in f.qualifiers.get("phrog")[0]
                or "acr" in f.qualifiers.get("phrog")[0]
                or "defensefinder" in f.qualifiers.get("phrog")[0]
            ):  # vfdb or card or acr or defensefinder
                data_dict["acr_defense_vfdb_card"]["fwd_list"].append(f)
            else:  # no vfdb or card
                if f.qualifiers.get("function")[0] == "unknown function":
                    data_dict["unk"]["fwd_list"].append(f)
                elif f.qualifiers.get("function")[0] == "other":
                    data_dict["other"]["fwd_list"].append(f)
                elif f.qualifiers.get("function")[0] == "tail":
                    data_dict["tail"]["fwd_list"].append(f)
                elif f.qualifiers.get("function")[0] == "transcription regulation":
                    data_dict["transcription"]["fwd_list"].append(f)
                elif (
                    "DNA" in f.qualifiers.get("function")[0]
                ):  # to make compatible with pharokka
                    data_dict["dna"]["fwd_list"].append(f)
                elif f.qualifiers.get("function")[0] == "lysis":
                    data_dict["lysis"]["fwd_list"].append(f)
                elif (
                    "moron" in f.qualifiers.get("function")[0]
                ):  # to make compatible with pharokka
                    data_dict["moron"]["fwd_list"].append(f)
                elif f.qualifiers.get("function")[0] == "integration and excision":
                    data_dict["int"]["fwd_list"].append(f)
                elif f.qualifiers.get("function")[0] == "head and packaging":
                    data_dict["head"]["fwd_list"].append(f)
                elif f.qualifiers.get("function")[0] == "connector":
                    data_dict["con"]["fwd_list"].append(f)

    for f in rev_features:
        if f.type == "CDS":
            if (
                "vfdb" in f.qualifiers.get("phrog")[0]
                or "card" in f.qualifiers.get("phrog")[0]
                or "acr" in f.qualifiers.get("phrog")[0]
                or "defensefinder" in f.qualifiers.get("phrog")[0]
            ):  # vfdb or card or acr or defensefinder
                data_dict["acr_defense_vfdb_card"]["rev_list"].append(f)
            else:  # no vfdb or card
                if f.qualifiers.get("function")[0] == "unknown function":
                    data_dict["unk"]["rev_list"].append(f)
                elif f.qualifiers.get("function")[0] == "other":
                    data_dict["other"]["rev_list"].append(f)
                elif f.qualifiers.get("function")[0] == "tail":
                    data_dict["tail"]["rev_list"].append(f)
                elif f.qualifiers.get("function")[0] == "transcription regulation":
                    data_dict["transcription"]["rev_list"].append(f)
                elif (
                    "DNA" in f.qualifiers.get("function")[0]
                ):  # to make compatible with pharokka
                    data_dict["dna"]["rev_list"].append(f)
                elif f.qualifiers.get("function")[0] == "lysis":
                    data_dict["lysis"]["rev_list"].append(f)
                elif (
                    "moron" in f.qualifiers.get("function")[0]
                ):  # to make compatible with pharokka
                    data_dict["moron"]["rev_list"].append(f)
                elif f.qualifiers.get("function")[0] == "integration and excision":
                    data_dict["int"]["rev_list"].append(f)
                elif f.qualifiers.get("function")[0] == "head and packaging":
                    data_dict["head"]["rev_list"].append(f)
                elif f.qualifiers.get("function")[0] == "connector":
                    data_dict["con"]["rev_list"].append(f)

    # add the tracks now
    # fwd
    for key in data_dict.keys():
        cds_track.genomic_features(
            data_dict[key]["fwd_list"],
            plotstyle="arrow",
            r_lim=(75, 80),
            fc=data_dict[key]["col"],
        )
        # rev
        cds_track.genomic_features(
            data_dict[key]["rev_list"],
            plotstyle="arrow",
            r_lim=(70, 75),
            fc=data_dict[key]["col"],
        )

    #### Extra Features
    ###################################################

    extras_col = "black"

    fwd_list = []
    for f in fwd_features:
        if f.type in ["tRNA", "tmRNA", "tmRNA"]:
            fwd_list.append(f)

    cds_track.genomic_features(
        fwd_list,
        plotstyle="arrow",
        r_lim=(75, 80),
        fc=extras_col,
    )

    rev_list = []
    for f in rev_features:
        if f.type in ["tRNA", "tmRNA", "tmRNA"]:
            rev_list.append(f)

    cds_track.genomic_features(
        rev_list,
        plotstyle="arrow",
        r_lim=(70, 75),
        fc=extras_col,
    )

    ##################################
    ####### thin out extra features #########
    ##################################

    if remove_other_features_labels == False:
        # trna
        pos_list_trna, labels_trna, length_list_trna = [], [], []
        for f in trna_features:
            start, end = int(str(f.location.end)), int(str(f.location.start))
            pos = (start + end) / 2.0
            length = end - start
            label = "tRNA"
            pos_list_trna.append(pos)
            labels_trna.append(label)
            length_list_trna.append(length)

        # if trnas exist
        if len(length_list_trna) > 0:
            # thin out the trnas to avoid overlaps
            # Create an empty list to store the filtered indices
            filtered_indices_trna = []
            # add the first tRNA
            filtered_indices_trna.append(0)

            for i in range(1, len(length_list_trna)):
                # If the position of the trna is at least 500bp away from the previous, add it
                if pos_list_trna[i] > (pos_list_trna[i - 1] + 500):
                    filtered_indices_trna.append(i)

            # Use the filtered indices to create new lists for pos_list, labels, and length_list
            pos_list_trna = [pos_list_trna[i] for i in filtered_indices_trna]
            labels_trna = [labels_trna[i] for i in filtered_indices_trna]
            length_list_trna = [length_list_trna[i] for i in filtered_indices_trna]

        # tmrna
        pos_list_tmrna, labels_tmrna, length_list_tmrna = [], [], []
        for f in tmrna_features:
            start, end = int(str(f.location.end)), int(str(f.location.start))
            pos = (start + end) / 2.0
            length = end - start
            label = "tmRNA"
            pos_list_tmrna.append(pos)
            labels_tmrna.append(label)
            length_list_tmrna.append(length)

        if len(length_list_tmrna) > 0:
            # thin out the trnas to avoid overlaps
            # Create an empty list to store the filtered indices
            filtered_indices_tmrna = []
            # add the first tmRNA
            filtered_indices_tmrna.append(0)

            for i in range(1, len(length_list_tmrna)):
                # If the position of the tmRNA is at least 500bp away from the previous, add it
                if pos_list_tmrna[i] > (pos_list_tmrna[i - 1] + 500):
                    filtered_indices_tmrna.append(i)

            # Use the filtered indices to create new lists for pos_list, labels, and length_list
            pos_list_tmrna = [pos_list_tmrna[i] for i in filtered_indices_tmrna]
            labels_tmrna = [labels_tmrna[i] for i in filtered_indices_tmrna]
            length_list_tmrna = [length_list_tmrna[i] for i in filtered_indices_tmrna]

        # crispr
        pos_list_crispr, labels_crispr, length_list_crispr = [], [], []
        for f in crispr_features:
            start, end = int(str(f.location.end)), int(str(f.location.start))
            pos = (start + end) / 2.0
            length = end - start
            label = "CRISPR"
            pos_list_crispr.append(pos)
            labels_crispr.append(label)
            length_list_crispr.append(length)

        if len(length_list_crispr) > 0:
            # thin out the crisprs to avoid overlaps
            # Create an empty list to store the filtered indices
            filtered_indices_crispr = []
            # add the first crispr
            filtered_indices_crispr.append(0)

            for i in range(1, len(length_list_tmrna)):
                # If the position of the crispr is at least 500bp away from the previous, add it
                if pos_list_crispr[i] > (pos_list_crispr[i - 1] + 500):
                    filtered_indices_crispr.append(i)

            # Use the filtered indices to create new lists for pos_list, labels, and length_list
            pos_list_crispr = [pos_list_crispr[i] for i in filtered_indices_crispr]
            labels_crispr = [labels_crispr[i] for i in filtered_indices_crispr]
            length_list_crispr = [
                length_list_crispr[i] for i in filtered_indices_crispr
            ]

    ##################################
    ####### truncate CDS labels
    ##################################

    # Extract CDS product labels
    pos_list, labels, length_list, id_list = [], [], [], []
    for f in cds_features:
        start, end = int(str(f.location.end)), int(str(f.location.start))
        pos = (start + end) / 2.0
        length = end - start
        label = f.qualifiers.get("product", [""])[0]
        id = f.qualifiers.get("ID", [""])[0]

        # skip hypotheticals if the flag is false (default)
        if id in label_force_list:  # if in the list
            if len(label) > truncate:
                label = label[:truncate] + "..."
            pos_list.append(pos)
            labels.append(label)
            length_list.append(length)
            id_list.append(id)
            continue  # to break if in the list
        else:
            if label_hypotheticals is False:
                if (
                    label == ""
                    or label.startswith("hypothetical")
                    or label.startswith("unknown")
                ):
                    continue  # if hypothetical not in the list
                else:  # all others
                    if len(label) > truncate:
                        label = label[:truncate] + "..."
                    pos_list.append(pos)
                    labels.append(label)
                    length_list.append(length)
                    id_list.append(id)

    ###################################################
    #### thin out CDS annotations
    ###################################################

    if annotations == 0:
        logger.info(
            "By inputting --annotations 0 you have chosen to plot no annotations. Continuing"
        )
    elif annotations > 1:
        logger.info(
            "You have input a --annotations value greater than 1. Setting to 1 (will plot all annotations). Continuing"
        )
        annotations = 1
    elif annotations < 0:
        logger.info(
            "You have input a --annotations value less than 0. Setting to 0 (will plot no annotations). Continuing"
        )
        annotations = 0

    ####### running the sparsity

    quantile_length = np.quantile(length_list, annotations)
    # Create an empty list to store the filtered indices
    filtered_indices = []

    # Loop through the indices of the length_list
    for i in range(len(length_list)):
        # If the length at this index is greater than or equal to the median, add the index to filtered_indices
        # captures the once in the label force list
        if (length_list[i] < quantile_length) or (id_list[i] in label_force_list):
            filtered_indices.append(i)

    # Use the filtered indices to create new lists for pos_list, labels, and length_list
    pos_list = [pos_list[i] for i in filtered_indices]
    labels = [labels[i] for i in filtered_indices]
    length_list = [length_list[i] for i in filtered_indices]

    # Plot CDS product labels on outer position
    cds_track.xticks(
        pos_list,
        labels,
        label_orientation="vertical",
        show_bottom_line=True,
        label_size=label_size,
        line_kws=dict(ec="grey"),
    )

    ###################################################
    # set other features
    ###################################################
    if remove_other_features_labels == False:
        # add trnas
        cds_track.xticks(
            pos_list_trna,
            labels_trna,
            label_orientation="vertical",
            show_bottom_line=True,
            label_size=label_size,
            line_kws=dict(ec="grey"),
        )
        # add tmrnas
        cds_track.xticks(
            pos_list_tmrna,
            labels_tmrna,
            label_orientation="vertical",
            show_bottom_line=True,
            label_size=label_size,
            line_kws=dict(ec="grey"),
        )
        # add crisprs
        cds_track.xticks(
            pos_list_crispr,
            labels_crispr,
            label_orientation="vertical",
            show_bottom_line=True,
            label_size=label_size,
            line_kws=dict(ec="grey"),
        )

    ###################################################
    # set gc content and skew coordinates
    ###################################################
    gc_content_start = 42.5
    gc_content_end = 60
    gc_skew_start = 25
    gc_skew_end = 42.5

    # Plot GC content
    gc_content_track = sector.add_track((gc_content_start, gc_content_end))
    pos_list, gc_contents = gbk.calc_gc_content(seq=contig_sequence)
    gc_contents = (
        gc_contents - SeqUtils.gc_fraction(contig_sequence) * 100
    )  # needs biopython >=1.80
    positive_gc_contents = np.where(gc_contents > 0, gc_contents, 0)
    negative_gc_contents = np.where(gc_contents < 0, gc_contents, 0)
    abs_max_gc_content = np.max(np.abs(gc_contents))
    vmin, vmax = -abs_max_gc_content, abs_max_gc_content
    gc_content_track.fill_between(
        pos_list, positive_gc_contents, 0, vmin=vmin, vmax=vmax, color="black"
    )
    gc_content_track.fill_between(
        pos_list, negative_gc_contents, 0, vmin=vmin, vmax=vmax, color="grey"
    )

    # Plot GC skew
    gc_skew_track = sector.add_track((gc_skew_start, gc_skew_end))

    pos_list, gc_skews = gbk.calc_gc_skew(seq=contig_sequence)
    positive_gc_skews = np.where(gc_skews > 0, gc_skews, 0)
    negative_gc_skews = np.where(gc_skews < 0, gc_skews, 0)
    abs_max_gc_skew = np.max(np.abs(gc_skews))
    vmin, vmax = -abs_max_gc_skew, abs_max_gc_skew
    gc_skew_track.fill_between(
        pos_list, positive_gc_skews, 0, vmin=vmin, vmax=vmax, color="green"
    )
    gc_skew_track.fill_between(
        pos_list, negative_gc_skews, 0, vmin=vmin, vmax=vmax, color="purple"
    )

    label_size = int(label_size)

    # Plot xticks & intervals on inner position
    cds_track.xticks_by_interval(
        interval=int(interval),
        outer=False,
        show_bottom_line=False,
        label_formatter=lambda v: f"{v/ 1000:.0f} Kb",  # no decimal place
        label_orientation="vertical",
        line_kws=dict(ec="grey"),
        label_size=7,
    )

    ################################
    # phrog legend
    ###############################

    # # Add legend
    handle_phrogs = [
        Patch(color=data_dict["unk"]["col"], label="Unknown Function"),
        Patch(color=data_dict["other"]["col"], label="Other Function"),
        Patch(
            color=data_dict["transcription"]["col"], label="Transcription Regulation"
        ),
        Patch(
            color=data_dict["dna"]["col"], label="DNA/RNA & nucleotide \n metabolism"
        ),
        Patch(color=data_dict["lysis"]["col"], label="Lysis"),
        Patch(
            color=data_dict["moron"]["col"],
            label="Moron, auxiliary metabolic \n gene & host takeover",
        ),
        Patch(color=data_dict["int"]["col"], label="Integration & excision"),
        Patch(color=data_dict["head"]["col"], label="Head & packaging"),
        Patch(color=data_dict["con"]["col"], label="Connector"),
        Patch(color=data_dict["tail"]["col"], label="Tail"),
        Patch(color=data_dict["acr_defense_vfdb_card"]["col"], label="VF/AMR/ACR/DF"),
    ]

    fig = circos.plotfig()

    phrog_legend_coords = (0.10, 1.185)
    phrog_legend = circos.ax.legend(
        handles=handle_phrogs,
        bbox_to_anchor=phrog_legend_coords,
        fontsize=9.5,
        loc="center",
        title="PHROG CDS",
        handlelength=2,
    )

    circos.ax.add_artist(phrog_legend)

    ################################
    # gc and other features legend
    ###############################

    handle_gc_content = [
        Line2D(
            [],
            [],
            color="black",
            label="Positive GC Content",
            marker="^",
            ms=6,
            ls="None",
        ),
        Line2D(
            [],
            [],
            color="grey",
            label="Negative GC Content",
            marker="v",
            ms=6,
            ls="None",
        ),
    ]

    handle_gc_skew = [
        Line2D(
            [], [], color="green", label="Positive GC Skew", marker="^", ms=6, ls="None"
        ),
        Line2D(
            [],
            [],
            color="purple",
            label="Negative GC Skew",
            marker="v",
            ms=6,
            ls="None",
        ),
    ]

    handle_other_features = [Patch(color=extras_col, label="tRNA/tmRNA/CRISPR")]

    # shrink plot a bit (0.8)
    box = circos.ax.get_position()
    circos.ax.set_position([box.x0, box.y0, box.width * 0.65, box.height * 0.9])

    # gc content and skew coordinates
    gc_content_anchor = (0.92, 1.30)
    gc_skew_anchor = (0.92, 1.20)

    gc_legend_cont = circos.ax.legend(
        handles=handle_gc_content,
        bbox_to_anchor=gc_content_anchor,
        loc="center",
        fontsize=9.5,
        title="GC Content",
        handlelength=2,
    )

    circos.ax.add_artist(gc_legend_cont)

    gc_legend_skew = circos.ax.legend(
        handles=handle_gc_skew,
        bbox_to_anchor=gc_skew_anchor,
        loc="center",
        fontsize=9.5,
        title="GC Skew",
        handlelength=2,
    )

    circos.ax.add_artist(gc_legend_skew)

    # other features
    other_features_anchor = (0.92, 1.10)

    other_features_legend = circos.ax.legend(
        handles=handle_other_features,
        bbox_to_anchor=other_features_anchor,
        loc="center",
        fontsize=9.5,
        title="Other Features",
        handlelength=2,
    )

    circos.ax.add_artist(other_features_legend)

    dpi = int(dpi)

    # save as png
    fig.savefig(png_plot_file, dpi=dpi)

    # Save the image as an SVG
    fig.savefig(svg_plot_file, format="svg", dpi=dpi)
