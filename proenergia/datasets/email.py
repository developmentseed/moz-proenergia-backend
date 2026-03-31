from typing import List

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse


def send_dataset_approval_email(
    dataset_name: str, dataset_id: int, email_list: List[str]
):
    link = reverse("admin:datasets_vectordataset_change", args=[dataset_id])
    url = f"{settings.BACKEND_URL}{link}"
    email = EmailMultiAlternatives(
        f"Dataset {dataset_name} waiting for approval",
        f"A new version of the dataset {dataset_name} has been uploaded and is waiting for approval. Access {url} to approve it.",
        f"{settings.UNFOLD.get('SITE_TITLE')} <do_not_reply@edm.co.mz>",
        email_list,
    )
    html_content = f"""
    <p>A new version of the dataset <b>{dataset_name}</b> has been uploaded and is waiting for approval.</p>
    <p>Access <a href="{url}">{url}</a> to approve it.</p>
    """
    email.attach_alternative(html_content, "text/html")
    email.send()
