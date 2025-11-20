import boto3
import os

bucket_name = "s3-bucket-bedrock-project-malli"  # <-- your bucket
prefix = "documents/"  # folder inside S3 where files will go

s3 = boto3.client("s3")

local_folder = os.path.join("spec-sheets")

for filename in os.listdir(local_folder):
    if filename.endswith(".pdf") or filename.endswith(".txt"):
        local_path = os.path.join(local_folder, filename)
        s3_key = f"{prefix}{filename}"

        print(f"Uploading {filename} to {s3_key}...")
        s3.upload_file(local_path, bucket_name, s3_key)

print("Upload completed successfully.")
