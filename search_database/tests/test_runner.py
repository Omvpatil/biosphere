import requests
import json

# Your 10 test cases
test_cases = [
    "Find papers about mice in space missions published in 2014.",
    "Show me research on microgravity and bone loss by CDKN1a/p21.",
    "Looking for articles about stem cell health and tissue regeneration in microgravity.",
    "What are the recent findings on microgravity and embryonic stem cells?",
    "Get me the latest research on RNA isolation in microgravity conditions.",
    "Find studies on spaceflight and oxidative stress in the heart.",
    "Show me papers on space radiation and its effects on the skeletal system.",
    "Looking for research on NASA life sciences translational research.",
    "What are the recent publications on the effects of microgravity on bone quality?",
    "Find me articles about the effects of spaceflight on gene expression.",
    "I am looking for research papers authored by John Smith on the impact of microgravity on human health published in the Journal of Aerospace Medicine between 2020 and 2023.",
    "Can you find articles about the psychological effects of long-term space missions on astronauts, specifically focusing on mental health and stress management, published in the last five years?",
    "Show me the latest studies on the effects of space radiation on the cardiovascular system in astronauts, with a focus on long-term missions and potential countermeasures.",
    "I need information on the role of exercise in mitigating muscle atrophy during extended space missions, including details on specific exercises and their effectiveness.",
    "Find research papers discussing the impact of microgravity on plant growth and development, particularly focusing on Arabidopsis thaliana and its genetic responses.",
    "What are the recent advancements in our understanding of how spaceflight affects the immune system, and are there any studies on potential countermeasures to these effects?",
    "Look for articles that explore the changes in gene expression profiles in mice exposed to spaceflight conditions, including both short-term and long-term missions.",
    "I am interested in finding studies on the effects of simulated microgravity on human cells, specifically looking at changes in cell cycle regulation and apoptosis.",
    "Can you provide me with research on the impact of space travel on the aging process, including any studies on telomere length and cellular senescence in astronauts?",
    "Find papers that discuss the role of the gut microbiome in maintaining astronaut health during long-duration space missions, and any changes observed in microbial composition.",
    "Show me the latest findings on the effects of cosmic radiation on the brain, including any studies on cognitive function and neurological health in astronauts.",
    "I am looking for research on the use of artificial gravity as a countermeasure to the physiological effects of microgravity, including studies on both human and animal models.",
    "Can you find articles that investigate the impact of spaceflight on the musculoskeletal system, focusing on bone density loss and muscle wasting in astronauts?",
    "What are the recent studies on the effects of spaceflight on the circadian rhythm and sleep patterns of astronauts, and any strategies to mitigate these effects?",
    "Look for research papers that examine the impact of spaceflight on the cardiovascular system, including changes in heart function and blood pressure regulation.",
    "Find studies on the effects of microgravity on the vestibular system and spatial orientation, including any research on the adaptation of astronauts to space conditions.",
    "I need information on the latest research about the effects of spaceflight on the human body, specifically focusing on the cardiovascular system and any potential countermeasures.",
    "Can you provide articles discussing the impact of long-duration space missions on the mental health and psychological well-being of astronauts, including any coping strategies or interventions?",
    "Show me the latest studies on the effects of space radiation on DNA damage and repair mechanisms in astronauts, including any potential long-term health risks.",
]

url = "http://127.0.0.1:8000/search/test"

for i, query in enumerate(test_cases, 1):
    print(f"\n--- Test {i} ---")
    print(f"Input: {query}")

    # Send the request to your local Django server
    response = requests.post(url, json={"user_query": query})

    if response.status_code == 200:
        # Print the extracted facets nicely formatted
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Failed with status code: {response.status_code}")
