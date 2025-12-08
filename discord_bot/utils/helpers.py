"""
Helper utilities for the Discord bot.
"""

import logging

logger = logging.getLogger(__name__)


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def split_message(message: str, max_length: int = 1900) -> list:
    """Split a long message into chunks for Discord"""
    if len(message) <= max_length:
        return [message]

    chunks = []
    while message:
        if len(message) <= max_length:
            chunks.append(message)
            break

        # Find a good break point (try to break at sentence end)
        chunk = message[:max_length]
        last_period = chunk.rfind('.')
        last_newline = chunk.rfind('\n')

        if last_period > max_length * 0.8:
            split_point = last_period + 1
        elif last_newline > max_length * 0.8:
            split_point = last_newline
        else:
            split_point = max_length

        chunks.append(message[:split_point])
        message = message[split_point:].lstrip()

    return chunks


async def send_paginated_response(interaction, content: str, title: str = ""):
    """Send a long response as multiple messages"""
    chunks = split_message(content)

    for i, chunk in enumerate(chunks):
        if i == 0 and title:
            part_header = f"{title} **Part {i+1}/{len(chunks)}**\n\n"
            await interaction.followup.send(f"{part_header}{chunk}")
        else:
            part_header = f"**Part {i+1}/{len(chunks)}**\n\n"
            await interaction.followup.send(f"{part_header}{chunk}")

