"""
Find barcode cluster duplicates (two different barcode sequences origin to the same droplet, tagging the
same tagmented long molecule).

Condition to call barcode duplicate:

Two positions (positions defined as a unique set of read_start, read_stop, mate_start, mate_stop))
at a maximum of W (--window, default 100kbp, between = max(downstream_pos)-max(downstream_pos)) bp
apart sharing more than one barcode (share = union(bc_set_pos1, bc_set_pos2)).
"""

from pysam import AlignmentFile, AlignedSegment
from argparse import ArgumentError
import logging
from collections import Counter, deque, OrderedDict, defaultdict
import pickle
from copy import deepcopy

from blr.utils import get_bamtag, print_stats, tqdm

logger = logging.getLogger(__name__)


def main(args):
    if not (args.output_pickle or args.output_merges):
        raise ArgumentError(None, "Arguments --output-merges and/or --output-pickle required")

    run_find_clusterdups(
        input=args.input,
        output_pickle=args.output_pickle,
        output_merges=args.output_merges,
        barcode_tag=args.barcode_tag,
        buffer_size=args.buffer_size,
        window=args.window,
    )


def run_find_clusterdups(
    input: str,
    output_pickle: str,
    output_merges: str,
    barcode_tag: str,
    buffer_size: int,
    window: int,
):
    logger.info("Starting Analysis")
    summary = Counter()
    positions = OrderedDict()
    chrom_prev = None
    pos_prev = 0
    barcode_graph = BarcodeGraph()
    buffer_dup_pos = deque()
    for read, mate in tqdm(paired_reads(input, summary), desc="Reading pairs"):
        barcode = get_bamtag(read, barcode_tag)
        if not barcode:
            summary["Non tagged reads"] += 2
            continue

        if mate.is_read1 and read.is_read2:
            orientation = "F"
        else:
            orientation = "R"

        summary["Reads analyzed"] += 2

        chrom_new = read.reference_name
        pos_new = read.reference_start

        # Store position (5'-ends of R1 and R2) and orientation ('F' or 'R') with is used to group
        # duplicates. Based on picard MarkDuplicates definition, see
        # https://sourceforge.net/p/samtools/mailman/message/25062576/
        current_position = (mate.reference_start, read.reference_end, orientation)

        if abs(pos_new - pos_prev) > buffer_size or chrom_new != chrom_prev:
            find_barcode_duplicates(positions, buffer_dup_pos, barcode_graph, window, summary)

            if chrom_new != chrom_prev:
                positions.clear()
                buffer_dup_pos.clear()
                chrom_prev = chrom_new

            pos_prev = pos_new

        if current_position not in positions:
            positions[current_position] = PositionTracker(current_position)
        positions[current_position].add_barcode(barcode)

    # Process last chunk
    find_barcode_duplicates(positions, buffer_dup_pos, barcode_graph, window, summary)

    # Write outputs
    if output_pickle:
        logger.info(f"Writing pickle object to {output_pickle}")
        with open(output_pickle, 'wb') as file:
            pickle.dump(barcode_graph.graph, file, pickle.HIGHEST_PROTOCOL)

    merge_dict = barcode_graph.get_merges()
    summary["Barcodes removed"] = len(merge_dict)

    if output_merges:
        logger.info(f"Writing merges to {output_merges}")
        with open(output_merges, 'w') as file:
            for old_barcode, new_barcode in merge_dict.items():
                print(old_barcode, new_barcode, sep=",", file=file)

    logger.info("Finished")
    print_stats(summary, name=__name__)


def paired_reads(path: str, summary):
    """
    Yield (forward_read, reverse_read) pairs for all properly paired read pairs in the input file.

    :param path: str, path to SAM file
    :param summary: dict
    :return: read, mate: both as pysam AlignedSegment objects.
    """
    cache = dict()
    with AlignmentFile(path) as openin:
        for read in openin:
            summary["Total reads"] += 1
            # Requirements: read mapped, mate mapped and read has barcode tag
            # Cache read if matches requirements, continue with pair.
            if read.query_name in cache:
                mate = cache.pop(read.query_name)
            else:
                if pair_is_mapped_and_proper(read, summary):
                    cache[read.query_name] = read
                continue
            if pair_orientation_is_fr(read, mate, summary):
                yield read, mate


def pair_is_mapped_and_proper(read: AlignedSegment, summary) -> bool:
    """
    Checks so read pair meets requirements before being used in analysis.
    :param read: pysam read
    :param summary: dict
    :return: bool
    """
    if read.is_unmapped:
        summary["Unmapped reads"] += 1
        return False

    if read.mate_is_unmapped:
        summary["Unmapped reads"] += 1
        return False

    if not read.is_proper_pair:
        summary["Reads not proper pair"] += 1
        return False
    return True


def pair_orientation_is_fr(read: AlignedSegment, mate: AlignedSegment, summary) -> bool:
    # Proper layout of read pair.
    # PAIR      |       mate            read
    # ALIGNMENTS|    ---------->      <--------
    # CHROMOSOME| ==================================>
    if not mate.is_reverse and read.is_reverse:
        return True
    summary["Reads with wrong orientation"] += 2
    return False


def find_barcode_duplicates(positions, buffer_dup_pos, barcode_graph, window: int, summary):
    """
    Parse positions to check for valid duplicate positions that can be quired to find barcodes to merge
    :param positions: list: Position to check for duplicates
    :param barcode_graph: dict: Tracks which barcodes should be merged.
    :param buffer_dup_pos: list: Tracks previous duplicate positions and their barcode sets.
    :param window: int: Max distance allowed between positions to call barcode duplicate.
    :param summary: dict
    """
    positions_to_remove = list()
    for position in positions.keys():
        tracked_position = positions[position]
        if tracked_position.has_updated_barcodes:
            if tracked_position.is_duplicate():
                seed_duplicates(
                    barcode_graph=barcode_graph,
                    buffer_dup_pos=buffer_dup_pos,
                    position=tracked_position.position,
                    position_barcodes=tracked_position.barcodes,
                    window=window
                )
            tracked_position.has_updated_barcodes = False
        else:
            positions_to_remove.append(position)

    for position in positions_to_remove:
        del positions[position]


class PositionTracker:
    """
    Stores barcodes related to a position. The position is considered duplicate if more than one barcode is present.
    """
    def __init__(self, position):
        self.position = position
        self.reads = 0
        self.barcodes = set()
        self.has_updated_barcodes = False

    def add_barcode(self, barcode: str):
        self.has_updated_barcodes = True
        self.reads += 2
        self.barcodes.add(barcode)

    def is_duplicate(self) -> bool:
        return len(self.barcodes) > 1


def seed_duplicates(barcode_graph, buffer_dup_pos, position, position_barcodes, window: int):
    """
    Builds up a merge dictionary for which any keys should be overwritten by their value. Also
    keeps all previous positions saved in a list in which all reads which still are withing the
    window size are saved.
    :param barcode_graph: dict: Tracks which barcodes should be merged.
    :param buffer_dup_pos: list: Tracks previous duplicate positions and their barcode sets.
    :param position: tuple: Positions (start, stop) to be analyzed and subsequently saved to buffer.
    :param position_barcodes: seq: Barcodes at analyzed position
    :param window: int: Max distance allowed between postions to call barcode duplicate.
    """

    pos_start_new = position[0]
    # Loop over list to get the positions closest to the analyzed position first. When position
    # are out of the window size of the remaining buffer is removed.
    for index, (compared_position, compared_barcodes) in enumerate(buffer_dup_pos):

        # Skip comparison against self.
        if position == compared_position:
            continue

        compared_position_stop = compared_position[1]
        if compared_position_stop + window >= pos_start_new:
            barcode_intersect = position_barcodes & compared_barcodes

            # If two or more unique barcodes are found, update merge dict
            if len(barcode_intersect) >= 2:
                barcode_graph.add_connected_barcodes(barcode_intersect)
        else:
            # Remove positions outside of window (at end of list) since positions are sorted.
            for i in range(len(buffer_dup_pos) - index):
                buffer_dup_pos.pop()
            break

    # Add new position at the start of the list.
    buffer_dup_pos.appendleft((position, position_barcodes))


class BarcodeGraph:
    def __init__(self, graph=None):
        self.graph = graph if graph else defaultdict(set)
        self._seen = set()

    def add_connected_barcodes(self, barcodes):
        for barcode in barcodes:
            self.graph[barcode].update(barcodes - set(barcode))

    def _update_component(self, nodes, component):
        """Breadth-first search of nodes"""
        new_nodes = set()
        for n in nodes:
            if n not in self._seen:
                self._seen.add(n)
                component.add(n)
                new_nodes |= self.graph[n]

        new_nodes = new_nodes.difference(component)

        if new_nodes:
            self._update_component(new_nodes, component)

    def components(self):
        """Generate all connected components of graph"""
        self._seen.clear()
        for node, neigbours in self.graph.items():
            if node not in self._seen:
                self._seen.add(node)
                component = {node}
                self._update_component(neigbours, component)
                yield component

    def get_merges(self):
        """Get dict of barcodes to merge in style of current_barcode -> new_barcode"""
        merges_dict = dict()
        for component in self.components():
            barcodes_sorted = sorted(component)
            barcode_min = barcodes_sorted[0]
            merges_dict.update({barcode: barcode_min for barcode in barcodes_sorted[1:]})
        return merges_dict

    def merge(self, other):
        """Merge BarcodeGraph objects"""
        for barcode, connected_barcodes in other.graph.items():
            self.graph[barcode] |= connected_barcodes

    @classmethod
    def from_graph(cls, graph):
        """Construct BarcodeGraph instance from existing graph"""
        return cls(deepcopy(graph))

    @classmethod
    def from_merges(cls, merges):
        """Construct BarcodeGraph instance from existing dict of merges"""
        graph = defaultdict(set)
        for current_barcode, new_barcode in merges.items():
            graph[current_barcode].add(new_barcode)
            graph[new_barcode].add(current_barcode)
        return cls(graph)


def add_arguments(parser):
    parser.add_argument(
        "input",
        help="Coordinate-sorted SAM/BAM file tagged with barcodes.")
    parser.add_argument(
        "--output-pickle",
        help="Output python dict of barcodes to merge as pickle object.")
    parser.add_argument(
        "--output-merges",
        help="Output a CSV log file containing all merges done. File is in format: {old barcode id},{new barcode id}")
    parser.add_argument(
        "-b", "--barcode-tag", default="BX",
        help="SAM tag for storing the error corrected barcode. Default: %(default)s")
    parser.add_argument(
        "-w", "--window", type=int, default=100000,
        help="Window size. Duplicate positions within this distance will be used to find cluster "
        "duplicates. Default: %(default)s")
    parser.add_argument(
        "--buffer-size", type=int, default=200,
        help="Buffer size for collecting duplicates. Should be around read length. "
        "Default: %(default)s")
