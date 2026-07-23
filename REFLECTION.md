# Reflection

In this project, I learnt quickly that the API documentation is succinct but also deficient in detail, this meant that finding important keys and labels needed to complete the project meant running a dry run of the request for one record and finding the keys manually via the terminal output. There were also two different end points to hit in order for me to get the data i needed, the search/companies/ endpoint and the advanced_search_companies endpoint. Both endpoints at times had different keys for the same type of value such as 'title' in search/companies being the same as 'company_name' in advanced_search_companies. This made me have to create a method to handle both possibilities to match to the same company name value, that was a fun thing to work out in the moment.

I also enjoyed getting some more practice with threading.Session objects, ThreadPoolExecutors and a custom rate limiter which I learnt to make in my recent big data analytics module. The rate limiter was fun to make because I essentially had to think both about concurrency using the mutex, and also hacking together a custom blocking deque, a collection I use in Java from the standard library but got to roll from scratch again in python. That was also a nice feeling.

## AI Usage

I used Claude from time to time to suggest better approaches than I had formulated to achieve a couple goals.

For example, to match the company names I initially intended on using a combined requirement; The company name must have at least 50 percent matching characters positionally with the candidate, and if the names have more than one word in them, at least one word must be an exact match both spelling and position-wise using the *re* module. 

Claude made clear that this was a flawed approach and it would serve me better to use either -:

[difflib.SequenceMatcher.ratio()](https://docs.python.org/3/library/difflib.html)

or 

[RapidFuzz](https://pypi.org/project/RapidFuzz/)

to compute the differences between the strings more accurately and efficiently.

Claude also helped me diagnose and fix bugs, especially when I had a test .env variable set that just wouldnt make the requests I needed. Claude helped me identify that the issue was not my environment and actually the key itself that was the issue, i was then able to un-set the test key then re-set the live key. This done using curl outside python and confirmed that it wasnt a code issue but a key issue.

Other bug fixes like: SIC_code/SIC_codes field mismatch, a legal_suffixes over-stripping bug and the missing exact-match tier in the confidence logic.

### Lookahead

Given more time, I would love to work out a better method for calculating confidence, in this attempt I was not able to find a better method for getting high confidence matched for companies that I know exist such as Arm Limited, I stagnated at a low to ambiguous confidence rating and a top candidate match of Lazy Arm Limited, even purging the titles of their suffixes didnt improve the matches past the point at which they sit, that is upsetting but given more time to I believe I can figure it out.