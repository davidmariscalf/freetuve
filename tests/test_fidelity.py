from app.fidelity import align_manual_transcript, verify_segments


def test_rejects_material_disagreement_between_caption_and_audio_asr():
    source = [{
        "start": 0.0,
        "end": 3.0,
        "text": "I did she's at rest room real quick.",
    }]
    asr = [{
        "start": 0.1,
        "end": 2.9,
        "text": "I need to use the restroom real quick.",
    }]

    assert verify_segments(source, asr) == []


def test_keeps_same_sentence_despite_minor_tokenization_difference():
    source = [{
        "start": 0.0,
        "end": 3.0,
        "text": "I need to use the rest room real quick.",
    }]
    asr = [{
        "start": 0.1,
        "end": 2.9,
        "text": "I need to use the restroom real quick.",
    }]

    verified = verify_segments(source, asr)

    assert len(verified) == 1
    assert verified[0]["text"] == "I need to use the restroom real quick."
    assert verified[0]["verification_similarity"] >= 0.80


def test_rejects_caption_that_omits_multiple_asr_words():
    source = [{
        "start": 0.0,
        "end": 3.0,
        "text": "We need finish this project today.",
    }]
    asr = [{
        "start": 0.1,
        "end": 2.9,
        "text": "We absolutely need to finish this project today.",
    }]

    assert verify_segments(source, asr) == []


def test_does_not_verify_unaligned_segments():
    source = [{"start": 0.0, "end": 2.0, "text": "Hello there."}]
    asr = [{"start": 10.0, "end": 12.0, "text": "Hello there."}]

    assert verify_segments(source, asr) == []


def test_manual_transcript_supplies_wording_but_keeps_asr_timestamps():
    manual = "I need to use the restroom real quick. Then we can continue with the lesson."
    asr = [
        {"start": 4.2, "end": 7.4, "text": "I need to use the rest room real quick"},
        {"start": 7.6, "end": 10.1, "text": "Then we can continue with lesson"},
    ]

    aligned = align_manual_transcript(manual, asr)

    assert len(aligned) == 2
    assert aligned[0]["start"] == 4.2
    assert aligned[0]["end"] == 7.4
    assert "restroom" in aligned[0]["text"]
    assert aligned[1]["start"] == 7.6
    assert aligned[1]["manual_similarity"] >= 0.65


def test_manual_transcript_rejects_unrelated_text():
    manual = "Completely unrelated words about weather and mountains."
    asr = [{"start": 1.0, "end": 3.0, "text": "Please open the window before class."}]

    assert align_manual_transcript(manual, asr) == []
