from pathlib import Path

from app.models.schema import VideoParams
from app.services import video


def test_branding_is_enabled_by_default_for_portrait_only():
    portrait = VideoParams(video_subject="Auction update")
    landscape = VideoParams(video_subject="Auction update", video_aspect="16:9")
    disabled = VideoParams(
        video_subject="Auction update", rh_essendon_branding=False
    )

    assert portrait.rh_essendon_branding is True
    assert video.should_apply_rh_essendon_branding(portrait) is True
    assert video.should_apply_rh_essendon_branding(landscape) is False
    assert video.should_apply_rh_essendon_branding(disabled) is False


def test_branding_uses_supplied_assets_and_required_subtitle_style():
    assets = video.rh_essendon_branding_assets()
    branded = video.rh_essendon_subtitle_params(
        VideoParams(
            video_subject="Auction update",
            font_name="STHeitiMedium.ttc",
            font_size=40,
            text_fore_color="#000000",
            text_background_color=False,
        ),
        assets,
    )

    for asset in (
        assets.opening,
        assets.watermark,
        assets.closing,
        assets.headline_font,
        assets.secondary_font,
        assets.subtitle_font,
    ):
        assert Path(asset).is_file()
    assert Path(assets.opening).name == "Ampersand animation_without bg.mov"
    assert Path(assets.watermark).name == "Ampersand-Gold-RGB.png"
    assert Path(assets.closing).name == "R&H_Charcoal 1080 x 1920 portrait.mp4"
    assert branded.font_name == "Raine&HorneRegular.ttf"
    assert branded.text_fore_color == "#FFFFFF"
    assert branded.text_background_color == "#2B2B2B"
    assert branded.rounded_subtitle_background is True
    assert branded.stroke_width == 0
    assert branded.font_size == 58


def test_brand_contact_title_uses_director_not_managing_director():
    assert video._RH_BRAND_CONTACT[1] == "Director and Auctioneer"


def test_rh_contact_card_copy_is_deliberate_and_safe_for_old_or_unknown_tasks():
    assert video.rh_essendon_contact_card_type(None) == video.RH_CONTACT_CARD_JAYDEN
    assert video.rh_essendon_contact_card_type("unknown") == video.RH_CONTACT_CARD_JAYDEN
    assert video.rh_essendon_contact_card_type("rh_essendon_office") == video.RH_CONTACT_CARD_OFFICE

    personal = video.rh_essendon_contact_card_content("jayden_manno")
    assert personal == (
        "Jayden Manno",
        "Director and Auctioneer",
        "0421 736 736",
        "Raine & Horne Essendon",
    )

    office = video.rh_essendon_contact_card_content("rh_essendon_office")
    assert office == ("Raine & Horne Essendon", "(03) 9374 1111")
    assert all("Jayden" not in text for text in office)
    assert all("0421" not in text for text in office)


def test_contact_card_identifier_round_trips_with_task_parameters():
    saved = VideoParams(
        video_subject="Office card",
        rh_final_contact_card=video.RH_CONTACT_CARD_OFFICE,
    ).model_dump(mode="json")
    restored = VideoParams.model_validate(saved)

    assert restored.rh_final_contact_card == video.RH_CONTACT_CARD_OFFICE
    # Models restored from pre-selector task data receive the approved personal
    # card by default, preserving historical R&H output behaviour.
    saved.pop("rh_final_contact_card")
    assert VideoParams.model_validate(saved).rh_final_contact_card == video.RH_CONTACT_CARD_JAYDEN
