import json
import re


def convert_abbreviated_number(abbrev_number):
    abbrev_number = abbrev_number.lower()
    multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000}
    if abbrev_number[-1] in multipliers:
        multiplier = multipliers[abbrev_number[-1]]
        return int(float(abbrev_number[:-1]) * multiplier)
    else:
        return int(abbrev_number)


def get_gpt_payload(prompt):
    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    data = {
        'model': 'gpt-4o',  # Change this line to specify the GPT-4o model
        'messages': messages,
        'max_tokens': 250
    }

    return json.dumps(data)


def get_rank(s):
    try:
        return int(s)
    except ValueError:
        return 0


def get_number_of_results(text: str) -> int:
    """
    Extracts the number of results from the given text.

    Possible inputs:
    - "49-96 of 105 results for"
    - "1-16 of 591 results for"
    - "1 result for"
    - "No results for"

    Parameters:
    - text (str): The input text containing the results information.

    Returns:
    - int: The number of results. Returns 0 if there are no results or the input format is not recognized.
    """
    # improve the accuracy of the text by converting it to lowercase
    text = text.lower()

    # Check for "no result"
    if "no result" in text:
        return 0

    # Check for "1 result"
    if "1 result" in text:
        return 1

    # Use regex to find the number of results in the other formats
    match = re.search(r'of (\d+) results for', text)
    if match:
        return int(match.group(1))

    # If no match is found, return 0
    return 0
