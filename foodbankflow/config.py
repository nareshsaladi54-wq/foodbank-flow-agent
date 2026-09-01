"""Runtime configuration. One place for the model id, region and data paths."""
import os
import pathlib

PKG_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = PKG_DIR / "data"

# Amazon Bedrock model. Override with MODEL_ID. The default is a cross-region
# inference profile that is on by default for new accounts in us-east-1 / us-west-2.
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

# A cheaper fallback used by tests / the no-model demo path never touches this.
FALLBACK_MODEL_ID = os.environ.get("FALLBACK_MODEL_ID", "us.amazon.nova-2-lite-v1:0")


def bedrock_model():
    """Build the Strands BedrockModel lazily so importing the package is cheap."""
    from strands.models import BedrockModel

    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.2)
