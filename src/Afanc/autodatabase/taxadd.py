import re
import gzip
import pandas as pd
from Bio import SeqIO, SeqRecord
from collections import defaultdict
from os import mkdir, chdir, path, walk, rename


def editFasta(infasta, outdir, taxid, taxname):
    """ Constructs fastas to build the kraken2 database from using the ncbi taxonomy ID
    """

    if infasta.endswith(".gz"):
        file = gzip.open(infasta, "rt")
        fasta_file = f"{outdir}/{taxid}_{path.basename(infasta).split('.gz')[0]}"
    else:
        file = open(infasta, "r")
        fasta_file = f"{outdir}/{taxid}_{path.basename(infasta)}"

    ## edit the headers in each fasta file then output with the taxID
    fasta_data = file.read()
    fasta_edit = re.sub(r"(>.+)", r"\1|kraken:taxid|{0}|{1}".format(taxid, taxname), fasta_data)
    fasta_file_fin = open(fasta_file, "w")
    fasta_file_fin.write(fasta_edit)

    file.close()

    return 0


def addTaxon(taxname, mother_clade_taxid, names_df, nodes_df):
    """ takes a taxon missing from the ncbi database, and the names dataframe, and adds the taxon
    to the database.
    """

    ## max_taxid increased by a factor of 10 to it's length - 1
    ## this should avoid future conflicts
    max_taxid = max(names_df[0])
    taxid = max_taxid + ( 10**(len(taxid)-1) )

    ## hacky way of dealing with this, but anything above species level should not be getting introduced into the tax db anyway
    if taxname.count(" ")>1:
        rank = "subspecies"
    elif taxname.count(" ")==1:
        rank = "species"
    else:
        rank = "no rank"

    names_dbline = pd.DataFrame([ [taxid, taxname, "", "scientific name", "NaN"] ])
    nodes_dbline = pd.DataFrame([ [taxid, mother_clade_taxid, rank, "", "1", "1", "1", "1", "1" ,"1", "1", "1", "" ] ])

    names_df = names_df.append(names_dbline)
    nodes_df = nodes_df.append(nodes_dbline)

    print(f"Added {taxname} to ncbi taxonomy database.")

    return str(taxid), names_df, nodes_df


def search_taxon(taxname, names_df):
    """ Takes a taxonomy id and searches for it in the names dataframe
    """
    ## find row with species name
    taxon_row = names_df[names_df[1] == taxname]

    ## return None if taxon cannot be found
    if taxon_row.empty:
        # print(f"{taxname} taxon not found!", end=" ")
        return None
    ## return the ncbi taxon ID number of it can be found
    else:
        return str(taxon_row.iloc[0, 0])


def getTaxidNames(taxname, mother_clade, names_df, nodes_df):
    """ Get ncbi taxonomy ID for this taxon
    """

    # remove underscore from taxname
    taxname = taxname.replace("_", " ")

    taxid = search_taxon(taxname, names_df)

    ## block for dealing with taxon missing from the ncbi taxonomy database
    if taxid == None:

        print(f"Cannot find {taxname} in ncbi taxonomy database.")

        ###  TAXADD BLOCK  ###
        ### IN DEVELOPMENT ###

        """
        ## check to see if a mother clade is given
        if mother_clade != None:
            ## find taxid for the mother clade
            mother_clade_unformatted = mother_clade.replace("_", " ")
            print(f"Attempting to find {mother_clade_unformatted} in ncbi taxonomy database...", end=" ")
            mother_taxid = search_taxon(mother_clade_unformatted, names_df)

            ## if no taxon exists for the mother clade, find taxid for the genus
            if mother_taxid == None:
                genus = mother_clade.split("_")[0]
                print(f"Attempting to find {genus} in ncbi taxonomy database...")
                genus_taxid = search_taxon(genus, names_df)

                ## if the genus does not exist within the ncbi taxonomy database, then call a fail
                if genus_taxid == None:
                    print(f"{genus} taxon not found! Failed to add to ncbi taxonomy database...")

                ## else if the genus does exist within the database, add both the mother and daughter taxa
                else:
                    print(f"Found {genus_taxid}.", end="\n")
                    mother_taxid, names_df, nodes_df = addTaxon(mother_clade_unformatted, genus_taxid, names_df, nodes_df)
                    taxid, names_df, nodes_df = addTaxon(taxname, mother_taxid, names_df, nodes_df)

            else:
                print(f"Found {mother_taxid}.", end="\n")
                taxid, names_df, nodes_df = addTaxon(taxname, mother_taxid, names_df, nodes_df)

        ## if no mother clade is given, try to find the genus in the taxonomy database
        else:
            genus = taxname.split(" ")[0]
            print(f"Attempting to find genus {genus} in ncbi taxonomy database...", end=" ")
            genus_taxid = search_taxon(genus, names_df)

            ## if the genus does not exist within the ncbi taxonomy database, then call a fail
            if genus_taxid == None:
                print(f"{genus} taxon not found! Failed to add to ncbi taxonomy database...")

            ## else if the genus does exist within the database, add both the mother and daughter taxa
            else:
                print(f"Found {genus_taxid}.", end="\n")
                taxid, names_df, nodes_df = addTaxon(taxname, genus_taxid, names_df, nodes_df)
        """

    return taxid, names_df, nodes_df


def writeSeq2taxid(scaffold_taxid_dict, outdir):
    """ Writes a new seqid2taxid.map file
    """

    with open(f"{outdir}/seqid2taxid.map", 'w') as fout:
        for taxid, scaffids in scaffold_taxid_dict.items():
            for scaffid in scaffids:
                print(f"{scaffid}\t{taxid}", file=fout)


def get_scaffold_ids(fasta):
    """ returns a list of scaffod ids
    """
    return [ rec.id for rec in SeqIO.parse(fasta, "fasta") ]


def writeDmp(names_df, nodes_df, outdir):
    """ Writes a new dmp files
    """

    with open(f"{outdir}/names.dmp", 'w') as fout:
        for index, row in names_df.iterrows():
            tmp_row = list([str(r) for r in row])[:-1]
            tmp_row.append("")
            newrow = "\t|\t".join(tmp_row)
            print(newrow, file=fout)

    with open(f"{outdir}/nodes.dmp", 'w') as fout:
        for index, row in nodes_df.iterrows():
            tmp_row = list([str(r) for r in row])[:-1]
            tmp_row.append("")
            newrow = "\t|\t".join(tmp_row)
            print(newrow, file=fout)


def readDmp(dmp_file):
    """ Read in nodes/names dmp files and return as a pandas dataframe
    """

    # read dmp into dataframe
    dmp_df = pd.read_csv(dmp_file, header=None, sep="|")
    # strip leading and trailing whitespace from all columns
    dmp_df = dmp_df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

    return dmp_df


def taxadd_Main(fasta_WDir, fasta_db_path, names_path, nodes_path):

    scaffold_taxid_dict = defaultdict(list)

    fasta_dict = defaultdict(list)

    names_df = readDmp(names_path)
    nodes_df = readDmp(nodes_path)

    for dir, subdirs, fastas in walk(fasta_db_path):
        taxon_rank = dir.split(fasta_db_path)[-1].split("/")
        taxname = taxon_rank[-1]

        if len(taxon_rank) > 1:
            mother_clade = taxon_rank[-2]
        else:
            mother_clade = None

        for fasta in fastas:
            infasta = path.join(dir, fasta)
            fasta_dict[taxname].append(infasta)

            # get the taxonomic ID
            taxid, names_df, nodes_df = getTaxidNames(taxname, mother_clade, names_df, nodes_df)

            ## collect scaffold ids for writing seqid2taxid.map file
            scaffold_ids = get_scaffold_ids(infasta)
            for scaffold_id in scaffold_ids:
                scaffold_taxid_dict[taxid].append(scaffold_id)

            ## errorStrategy : Ignore equivilent
            ## TODO: add taxa to names and nodes
            if taxid == None:
                continue

            editFasta(infasta, fasta_WDir, taxid, taxname)

    ## rename the old names.dmp file
    dirpath = "/".join(names_path.split("/")[:-1])
    rename(names_path, f"{dirpath}/names.dmp.old")
    rename(nodes_path, f"{dirpath}/nodes.dmp.old")

    ## write the new nodes.dmp file
    writeDmp(names_df, nodes_df, dirpath)

    ## write new seq2taxid.map file
    writeSeq2taxid(scaffold_taxid_dict, dirpath)

    return fasta_dict
