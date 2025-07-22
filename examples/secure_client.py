import asyncio

from astmio.client import create_client


async def main():
    """
    A simple client to connect to the full-featured server.
    """
    # This is an example of a real message from a Mindray BS-240
    records = [
        [
            "H",
            r"|\^&",
            "",
            "",
            "Mindry^^",
            "",
            "",
            "",
            "",
            "",
            "",
            "PR",
            "1394-97",
            "20230507173105",
        ],
        [
            "P",
            "1",
            "",
            "",
            "",
            "Doe^John",
        ],  # Simplified to match profile fields
        [
            "O",
            "1",
            "12345",
            "",
            "^^^SARS-CoV-2",
            "R",
            "",
            "",
            "",
            "",
            "",
            "N",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "20230507100000",
        ],
        ["L", "1", "N"],
    ]

    # The new, simplified client creation
    client = create_client(port=5001, certfile=None)

    try:
        sent = await client.send(records)
        if sent:
            print("Successfully sent records to the server.")
        else:
            print("Failed to send records to the server.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if client._writer:
            client.close()
            await client.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
