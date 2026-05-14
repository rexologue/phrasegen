export PHONE_EXTRACTION_CASES_PATH="$PWD/output/cases.jsonl"
export PHONE_EXTRACTION_USED_PATH="$PWD/output/used.jsonl"
export PHONE_EXTRACTION_ACCEPTED_PATH="$PWD/output/accepted_mapping.jsonl"

cd ../..

python generate.py --config generations/phone_extraction/config.yaml