import os
import subprocess
import sys
import tempfile
from collections import defaultdict

# host system dependencies: requires `pdftk` to be installed and findable in the PATH

dont_match_message = "\n* * * * * * * * * *\nPDFs don't match!\n* * * * * * * * * *"
do_match_message = "\n* * * * * * * * * *\nPDFs match!\n* * * * * * * * * *"


def uncompress_pdf(input_pdf_path, output_pdf_path):
    try:
        subprocess.check_call(
            ["pdftk", input_pdf_path, "output", output_pdf_path, "uncompress"]
        )
    except subprocess.CalledProcessError as exc:
        print(f"Failed to uncompress {input_pdf_path}: {exc}")
        sys.exit(1)
    return output_pdf_path


def compare_pdfs(pdf1, pdf2):
    dont_match = False
    pdf_objs = {pdf1: [], pdf2: []}

    objs_by_type = {
        pdf1: defaultdict(list),
        pdf2: defaultdict(list),
    }

    for pdf_file in [pdf1, pdf2]:
        with open(pdf_file, mode="rb") as f:
            in_obj = False
            cur_obj = []
            cur_object_type = ""
            contains_stream = False

            for line_no, byte_string in enumerate(f):
                # Check for object start
                if b"obj" in byte_string and not in_obj:
                    in_obj = True
                    cur_obj = []

                if in_obj:
                    cur_obj.append(byte_string)
                    if b"/Type" in byte_string:
                        cur_object_type = (
                            byte_string.decode("utf-8").strip().split(" ")[1][1:]
                        )

                    if b"stream" in byte_string:
                        contains_stream = True

                # Check for object end
                if b"endobj" in byte_string:
                    in_obj = False
                    if not cur_object_type:
                        cur_object_type = "_none_"

                    pdf_objs[pdf_file].append((line_no, cur_obj, cur_object_type))
                    objs_by_type[pdf_file][cur_object_type].append(
                        (line_no, b"\n".join(cur_obj), contains_stream)
                    )
                    cur_obj = []
                    cur_object_type = ""
                    contains_stream = False

    print(f"pdf1={pdf1}")
    print(f"pdf2={pdf2}")
    print()

    # first compare the types of objects in each pdf. if they don't match, then the pdfs don't match.
    pdf1_obj_types = set(obj[2] for obj in pdf_objs[pdf1])
    pdf2_obj_types = set(obj[2] for obj in pdf_objs[pdf2])

    in_pdf1_but_not_pdf2 = pdf1_obj_types - pdf2_obj_types
    in_pdf2_but_not_pdf1 = pdf2_obj_types - pdf1_obj_types

    if in_pdf1_but_not_pdf2:
        dont_match = True
        print(
            f"pdf1 has object type(s) '{", ".join(list(in_pdf1_but_not_pdf2))}' that pdf2 doesn't have"
        )
    if in_pdf2_but_not_pdf1:
        dont_match = True
        print(
            f"pdf2 has object type(s) '{", ".join(list(in_pdf2_but_not_pdf1))}' that pdf1 doesn't have"
        )

    if dont_match:
        print(dont_match_message)
        sys.exit(1)

    # invariant now: the PDFs contain the same object types

    # now compare the number of objects of each type
    for obj_type in pdf1_obj_types:
        set1 = set(objs_by_type[pdf1][obj_type])
        set2 = set(objs_by_type[pdf2][obj_type])

        in_set1_but_not_set2 = set1 - set2
        in_set2_but_not_set1 = set2 - set1

        if in_set1_but_not_set2:
            dont_match = True
            print(
                f"pdf1 has {len(in_set1_but_not_set2)} different {obj_type} object(s)"
            )
            for x in in_set1_but_not_set2:
                if x[2]:
                    print(f"    - object with stream, len_bytes(object)={len(x[1])}\n")
                else:
                    print(f"    - {x}\n")

        if in_set2_but_not_set1:
            dont_match = True
            print(
                f"pdf2 has {len(in_set2_but_not_set1)} different {obj_type} object(s)"
            )
            for x in in_set2_but_not_set1:
                if x[2]:
                    print(f"    - object with stream, len_bytes(object)={len(x[1])}\n")
                else:
                    print(f"    - {x}\n")

    if dont_match:
        print(dont_match_message)
        sys.exit(1)

    # invariant now: the PDFs have the same number of objects of each object type

    # compare the contents of each object
    for obj_type in pdf1_obj_types:
        zipped_objs = zip(
            sorted(objs_by_type[pdf1][obj_type], key=lambda x: x[0]),
            sorted(objs_by_type[pdf2][obj_type], key=lambda x: x[0]),
        )
        for z1, z2 in zipped_objs:
            if z1[0] != z2[0]:
                dont_match = True
                print(f"Object {z1[1]} and {z2[1]} don't match\n")

    if dont_match:
        print(dont_match_message)
        sys.exit(1)
    else:
        print(do_match_message)
        sys.exit(0)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python main.py PDF1 PDF2")
        sys.exit(1)

    # TODO: check whether `pdftk` is installed and findable in the PATH

    pdf1 = sys.argv[1]
    pdf2 = sys.argv[2]

    # TODO: verify that files exist and are readable

    # TODO: look in the first few bytes and confirm that we probably have PDF files

    with tempfile.TemporaryDirectory() as temp_dir:
        pdf1_uncompressed = os.path.join(
            temp_dir, os.path.basename(pdf1).replace(".pdf", "-unc.pdf")
        )
        pdf2_uncompressed = os.path.join(
            temp_dir, os.path.basename(pdf2).replace(".pdf", "-unc.pdf")
        )

        # Uncompress PDF files
        pdf1_uncompressed = uncompress_pdf(pdf1, pdf1_uncompressed)
        pdf2_uncompressed = uncompress_pdf(pdf2, pdf2_uncompressed)

        compare_pdfs(pdf1_uncompressed, pdf2_uncompressed)
