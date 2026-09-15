from app.fidelity import verify_segments


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
    assert verified[0]["verification_similarity"] >= 0.68


def test_does_not_verify_unaligned_segments():
    source = [{"start": 0.0, "end": 2.0, "text": "Hello there."}]
    asr = [{"start": 10.0, "end": 12.0, "text": "Hello there."}]

    assert verify_segments(source, asr) == []
