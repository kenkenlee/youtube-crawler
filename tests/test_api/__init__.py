import pytest
from app.models.channel import Channel


def test_create_channel(client, sample_channel_data):
    """Test creating a new channel"""
    response = client.post("/api/channels/", json=sample_channel_data)
    assert response.status_code == 201
    data = response.json()
    assert data["channel_id"] == sample_channel_data["channel_id"]
    assert data["channel_name"] == sample_channel_data["channel_name"]


def test_list_channels(client, db, sample_channel_data):
    """Test listing channels"""
    # Create a channel first
    channel = Channel(**sample_channel_data)
    db.add(channel)
    db.commit()

    # List channels
    response = client.get("/api/channels/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_channel(client, db, sample_channel_data):
    """Test getting a specific channel"""
    # Create a channel
    channel = Channel(**sample_channel_data)
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Get the channel
    response = client.get(f"/api/channels/{channel.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["channel_id"] == sample_channel_data["channel_id"]


def test_update_channel(client, db, sample_channel_data):
    """Test updating a channel"""
    # Create a channel
    channel = Channel(**sample_channel_data)
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Update the channel
    update_data = {"channel_name": "Updated Channel Name"}
    response = client.put(f"/api/channels/{channel.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["channel_name"] == "Updated Channel Name"


def test_delete_channel(client, db, sample_channel_data):
    """Test deleting a channel"""
    # Create a channel
    channel = Channel(**sample_channel_data)
    db.add(channel)
    db.commit()
    db.refresh(channel)

    # Delete the channel
    response = client.delete(f"/api/channels/{channel.id}")
    assert response.status_code == 204

    # Verify it's deleted
    response = client.get(f"/api/channels/{channel.id}")
    assert response.status_code == 404


def test_create_channel_duplicate(client, db, sample_channel_data):
    """Test creating a duplicate channel"""
    # Create first channel
    channel = Channel(**sample_channel_data)
    db.add(channel)
    db.commit()

    # Try to create duplicate
    response = client.post("/api/channels/", json=sample_channel_data)
    assert response.status_code == 400
