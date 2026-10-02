from fastapi import APIRouter

from app.schemas.legal_pages import LegalPageResponse

router = APIRouter(tags=["legal"])

_LAST_UPDATED = "2026-03-29"

_PAGES: dict[str, LegalPageResponse] = {
    "privacy": LegalPageResponse(
        slug="privacy",
        title="Privacy Policy",
        last_updated=_LAST_UPDATED,
        summary="How Symple One collects, uses, and protects data when you use our services.",
        sections=[
            {
                "heading": "Information we collect",
                "body": (
                    "We collect account information you provide (such as name and email), "
                    "operational data needed to connect and manage Amazon seller accounts, "
                    "and standard technical logs (for example IP address and request metadata) "
                    "to secure and operate the service."
                ),
            },
            {
                "heading": "Amazon seller data",
                "body": (
                    "When you authorize Symple One with Amazon, we receive OAuth tokens and "
                    "seller identifiers required to act on your behalf via the Selling Partner API. "
                    "Refresh tokens are stored encrypted on our servers and are not exposed to "
                    "your browser or third parties."
                ),
            },
            {
                "heading": "How we use information",
                "body": (
                    "We use data to authenticate users, fulfill authorized seller workflows, "
                    "improve reliability, comply with law, and respond to support requests. "
                    "We do not sell personal information."
                ),
            },
            {
                "heading": "Retention and security",
                "body": (
                    "We retain data while your account is active and as required for legal or "
                    "operational purposes. We apply access controls, encryption for sensitive "
                    "credentials, and monitoring appropriate to a production API."
                ),
            },
            {
                "heading": "Contact",
                "body": "Privacy questions: support@sympleone.com",
            },
        ],
    ),
    "terms": LegalPageResponse(
        slug="terms",
        title="Terms of Service",
        last_updated=_LAST_UPDATED,
        summary="Terms governing use of the Symple One platform and APIs.",
        sections=[
            {
                "heading": "Acceptance",
                "body": (
                    "By accessing or using Symple One, you agree to these terms. If you use the "
                    "service on behalf of an organization, you represent that you have authority "
                    "to bind that organization."
                ),
            },
            {
                "heading": "Permitted use",
                "body": (
                    "You may use Symple One only for lawful seller operations you are authorized "
                    "to perform. You must comply with Amazon's policies and applicable laws when "
                    "connecting seller accounts and using integrated features."
                ),
            },
            {
                "heading": "Accounts and security",
                "body": (
                    "You are responsible for safeguarding login credentials and for activity under "
                    "your account. Notify us promptly of unauthorized access."
                ),
            },
            {
                "heading": "Disclaimer",
                "body": (
                    "The service is provided as-is to the extent permitted by law. We do not "
                    "guarantee uninterrupted or error-free operation."
                ),
            },
            {
                "heading": "Changes",
                "body": (
                    "We may update these terms. Continued use after the last_updated date "
                    "constitutes acceptance of the revised terms."
                ),
            },
        ],
    ),
    "support": LegalPageResponse(
        slug="support",
        title="Support",
        last_updated=_LAST_UPDATED,
        summary="How to get help with Symple One.",
        sections=[
            {
                "heading": "Email",
                "body": "For product and account support, email support@sympleone.com.",
            },
            {
                "heading": "Amazon authorization",
                "body": (
                    "If Amazon seller connection fails, confirm your organization admin has "
                    "completed authorization and that redirect URLs match your deployed API "
                    "configuration (AMAZON_REDIRECT_URI)."
                ),
            },
            {
                "heading": "Security issues",
                "body": (
                    "Report suspected security vulnerabilities to support@sympleone.com. "
                    "Do not include passwords or refresh tokens in email."
                ),
            },
        ],
        contact_email="support@sympleone.com",
    ),
}


@router.get("/privacy", response_model=LegalPageResponse)
def privacy_policy() -> LegalPageResponse:
    return _PAGES["privacy"]


@router.get("/terms", response_model=LegalPageResponse)
def terms_of_service() -> LegalPageResponse:
    return _PAGES["terms"]


@router.get("/support", response_model=LegalPageResponse)
def support() -> LegalPageResponse:
    return _PAGES["support"]
