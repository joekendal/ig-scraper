import boto3


def upload_file(file_path, bucket, object_name, metadata):
    """
    Upload a file to an S3 bucket

    :param  file_path   str     File to upload
    :param  bucket      str     Bucket to upload to
    :param  object_name str     S3 object name
    """

    s3 = boto3.client('s3')

    if metadata['type'] == 'Image':
        content_type = 'image/jpeg'
    elif metadata['type'] == 'Video':
        content_type = 'video/mpeg'
    else:
        content_type = None

    response = s3.upload_file(
        file_path, bucket, object_name,
        ExtraArgs={
            'Metadata': metadata,
            'ContentType': content_type
        }
    )

    return True
