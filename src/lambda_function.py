import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Final

import boto3
import botocore
from botocore.config import Config
from botocore.exceptions import ClientError
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter

AWS_S3_BUCKET: Final[str] = os.getenv('AWS_S3_BUCKET')
RESUME_DIRECTORY: Final[str] = os.getenv(
    'RESUME_DIRECTORY')
OUTPUT_DIRECTORY_S3: Final[str] = os.getenv('OUTPUT_DIRECTORY_S3')

# Normal S3 client
normal_s3_config = Config(connect_timeout=5, retries={'max_attempts': 0})
s3_client = boto3.client('s3', config=normal_s3_config)

# Unsigned link S3 client for generating the URL to the uploaded converted resume
# Credit: https://stackoverflow.com/a/48197877
unsigned_url_s3_config = Config(signature_version=botocore.UNSIGNED)
unsigned_url_s3_config.signature_version = botocore.UNSIGNED
unsigned_url_s3_client = boto3.client('s3', config=unsigned_url_s3_config)


def lambda_handler(event, context):
    # The file name of the resume to convert on S3
    s3_filename: str = event['fileToConvert']

    # Original resume file data
    original_path = f'/tmp/{s3_filename}'
    original_filename_stem = Path(original_path).stem
    original_filename_ext = Path(original_path).suffix

    # Converted resume file data
    converted_filename = f"{original_filename_stem}.pdf"
    converted_path = f"/tmp/{converted_filename}"

    # S3 Keys
    s3_original_key = f'{RESUME_DIRECTORY}/{s3_filename}'
    s3_converted_key = f"{OUTPUT_DIRECTORY_S3}/{converted_filename}"

    # Download file to /tmp and get data from the filename
    print(
        f'Downloading resume "{s3_filename}" from AWS S3 bucket from key "{s3_original_key}"')
    s3_client.download_file(AWS_S3_BUCKET, s3_original_key, original_path)
    print("Successfully downloaded resume.")

    # Convert based on file type
    if (original_filename_ext in ('.docx', ".doc", ".odt", ".rtf")):
        # TODO: Convert using Libreoffice
        print('Libreoffice')
    elif (original_filename_ext in ('.png', '.jpg', '.jpeg')):
        # TODO: Convert using img2pdf
        print('img2pdf')
    elif (original_filename_ext == ".pages"):
        # TODO: Extract preview and convert using img2pdf
        print('pages')
    elif (original_filename_ext == ".txt"):
        # TODO: Convert using reportlab
        print("Converting text file to PDF...")
        convert_txt_to_pdf(converted_path, original_path)
        print("Conversion complete.")
    else:
        return {
            'statusCode': 400,
            'body': json.dumps('No supported files found to convert.')
        }

    # Upload result to AWS S3
    try:
        print("Uploading converted resume to AWS S3 bucket...")
        s3_client.upload_file(converted_path, AWS_S3_BUCKET,
                              s3_converted_key)
        print("Successfully uploaded resume.")

        # Get uploaded file name
        s3_converted_pdf_url: str = unsigned_url_s3_client.generate_presigned_url('get_object', ExpiresIn=0, Params={
            'Bucket': AWS_S3_BUCKET, 'Key': s3_converted_key})

        print(f"Converted PDF URL: {s3_converted_pdf_url}")

        return {
            'statusCode': 200,
            'body': json.dumps(f'Resume successfully converted and uploaded to AWS S3 bucket at URL: {s3_converted_pdf_url}')
        }
    except ClientError as e:
        print(e)
        return {
            'statusCode': 502,
            'body': json.dumps('Could not upload to AWS S3 bucket!')
        }


def convert_txt_to_pdf(input_txt_file: str, output_pdf_file: str):
    """
    Converts a .txt file to a PDF using Reportlab.
    Credit: https://stackoverflow.com/questions/51740145/how-can-i-write-text-to-pdf-file/51801140

    Arguments:
        input_txt_file {string} -- The location of the .txt file to convert.
        output_pdf_file {string} -- The output PDF file to write to.
    """
    print(f'Converting .txt file at "{input_txt_file}"')
    styles = getSampleStyleSheet()
    styleN = styles['Normal']
    story = []

    document = SimpleDocTemplate(
        output_pdf_file,
        pagesize=letter,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
        leftMargin=1 * inch,
        rightMargin=1 * inch
    )

    # Read the text file to memory
    file_to_convert = open(input_txt_file, 'r')
    content = file_to_convert.read()
    file_to_convert.close()

    paragraph = Paragraph(content, styleN)
    story.append(paragraph)

    document.build(story)

    print(f'Saved converted resume to "{output_pdf_file}"')
