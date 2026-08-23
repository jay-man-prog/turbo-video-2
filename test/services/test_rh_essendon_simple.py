from app.services import rh_essendon
from app.models.schema import MaterialInfo, VideoAspect
from app.services import material


def test_planner_keeps_sentences_in_script_order_and_uses_property_queries():
    script = (
        "Before Saturday, clear the kitchen bench. "
        "Then open the curtains in the living room. "
        "Finally, tidy the front garden."
    )

    beats = rh_essendon.plan_visual_beats(script, "Seller Tip")

    assert [beat.sentence for beat in beats] == [
        "Before Saturday, clear the kitchen bench.",
        "Then open the curtains in the living room.",
        "Finally, tidy the front garden.",
    ]
    assert all("Australian residential property" in beat.query for beat in beats)
    assert all("homeowner preparing house for sale" in beat.fallback_query for beat in beats)
    assert all(2 <= beat.duration <= 4 for beat in beats)


def test_market_update_prompt_requires_only_supplied_facts_and_no_phone_narration():
    prompt = rh_essendon.simple_script_prompt(
        "Market Update", 30, "Auction clearance rate supplied by the user: 61%."
    )

    assert "include no market fact unless it is in the supplied facts" in prompt
    assert "Never invent market statistics" in prompt
    assert "Do not narrate a phone number" in prompt


def test_visual_terms_include_ordered_primary_queries_and_graceful_fallbacks():
    beats = rh_essendon.plan_visual_beats(
        "Inspect the bright kitchen. Walk through the quiet garden.", "Buyer Tip"
    )

    terms = rh_essendon.visual_terms(beats)

    assert [term["query"] for term in terms] == [beat.query for beat in beats]
    assert [term["fallback_query"] for term in terms] == [beat.fallback_query for beat in beats]
    assert all(term["fallback_query"] for term in terms)


def test_ordered_downloader_uses_a_fallback_without_repeating_a_clip(monkeypatch):
    searches = []
    shared = MaterialInfo(provider="pexels", url="https://example.test/shared.mp4", duration=4)
    unique = MaterialInfo(provider="pexels", url="https://example.test/unique.mp4", duration=4)

    def search_videos(search_term, minimum_duration, video_aspect):
        searches.append(search_term)
        if search_term == "exact kitchen":
            return []
        if search_term == "fallback home":
            return [shared]
        return [shared, unique]

    monkeypatch.setattr(material, "save_video", lambda video_url, save_dir: f"/tmp/{video_url.rsplit('/', 1)[-1]}")
    monkeypatch.setattr(material, "_persist_material_sources", lambda *args: None)

    paths = material._download_videos_by_script_order(
        task_id="local-test",
        search_terms=[
            {"query": "exact kitchen", "fallback_query": "fallback home"},
            {"query": "garden", "fallback_query": "fallback home"},
        ],
        search_videos=search_videos,
        video_aspect=VideoAspect.portrait,
        audio_duration=7,
        max_clip_duration=3,
        material_directory="",
    )

    assert searches[:3] == ["exact kitchen", "fallback home", "garden"]
    assert paths == ["/tmp/shared.mp4", "/tmp/unique.mp4"]


def test_semantic_plan_uses_mocked_llm_json_and_keeps_alternates(monkeypatch):
    from app.services import llm

    monkeypatch.setattr(
        llm,
        "_generate_response",
        lambda prompt: '''[{"narration":"Open the curtains and let natural light fill the living room.","query":"woman opening curtains bright living room","alternates":["sunlight through curtains modern lounge","bright staged living room natural light"],"fallback":"bright residential living room","duration":4}]''',
    )

    plan = rh_essendon.generate_semantic_visual_plan("Open the curtains and let natural light fill the living room.", "Seller Tip", 30)

    assert plan[0]["query"] == "woman opening curtains bright living room"
    assert len(plan[0]["alternates"]) == 2


def test_finished_audio_duration_controls_beat_timing():
    durations = rh_essendon.allocate_beat_durations(
        [{"narration": "Short beat."}, {"narration": "This beat contains substantially more spoken words for timing."}],
        12,
    )

    assert len(durations) == 2
    assert durations[1] > durations[0]
    assert all(duration >= 2 for duration in durations)


def test_twenty_second_default_has_word_and_scene_targets():
    prompt = rh_essendon.simple_script_prompt("Seller Tip", 20, "")
    assert "45–52 words" in prompt


def test_simple_prompt_requests_upbeat_natural_delivery():
    assert "bright, positive" in rh_essendon.RH_SIMPLE_SYSTEM_PROMPT
    assert "sales-announcer voice" in rh_essendon.RH_SIMPLE_SYSTEM_PROMPT
