# UKSC-Coding-Test
## Gabi Fabiyi UKSC Coding Test

This program utilises the Companies House API to obtain information about a number of registered legal entities in the UK.

The code in main.py uses a matching/ranking qualifier to match company names to likely candidates and queries the API enpoints to retrieve the required data.


### 1. Clone the Repository

This repository can be cloned and run in your local environment and output is written to data/matched_companies.csv, with progress logged to the terminal as each record completes. 

In order to do this, you will require an API key from Companies House, instructions on creating an application and acquiring an API key can be found here: [Companies House API](https://developer.company-information.service.gov.uk/authentication/)

### 2. Create and Set the Environment Variable to the API Key

Once acquired, you can create a file named ".env" in the project root directory, and store the API key using UKSC_KEY as the key and the API key as the value e.g.: UKSC_KEY=myapi-key-myapi-key

then run:

export UKSC_KEY=your-key-here

Once you have your API key from Companies House, you will then be ready to run the program.

### 3. Set Up Your Local Environment

Start by ensuring python and pip are installed and up to date, you can do so by running the commands below:

(Check if python is installed on your machine): 

python --version

If you have python installed you should see output like: 

*Python 3.14.13* (or another 3.--.-- version)

If not install python here: [Python Download](https://www.python.org/downloads/)

Create and activate a virtual environment (this allows you to have a secluded environment to work in and download tailored installs for your project) - run:

python -m venv .venv

Then to activate the virtual environment - run:

source .venv/bin/activate

Your terminal line should now look something like:

(( venv )) your-current-directory % _

(Check if pip - the python package manager - is installed on your machine):

pip --version

If pip is installed you should see output like:

*pip 25.0.1 from path/to/pip (python 3.14)*

If not, install pip:

python -m ensurepip --upgrade 
(or py -m ensurepip --upgrade on Windows)

### 4. Download the required packages

Once you have installed pip and python, download the dependencies defined in requirements.txt - run:

pip install -r requirements.txt

### 5. Run the program

Once the dependencies have been installed, you can run the code and see the output in your terminal - run:

python src/main.py

## Match confidence methodology

For each input name, candidate UK entities are retrieved from Companies House's search endpoints, then scored against the normalised input using RapidFuzz (character-ratio, token-sort, and token-set similarity, taking the best of the three).

High: the normalised input matches a candidate's normalised name exactly, with no other candidate also matching exactly.
Low: ambiguous: the best candidate scores well but ties with (or scores within a small margin of) another equally plausible candidate.
None: no candidate scored above the similarity floor.
Error: the lookup failed (API error); the original record is still preserved.

This intentionally favours declaring a match ambiguous over guessing, per the brief's instruction not to force a match where evidence is insufficient.