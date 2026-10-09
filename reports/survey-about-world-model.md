# Survey of World Models

## TL;DR
- World models are foundational frameworks that construct internal representations to enhance interaction with complex environments [1].
- A variety of methodologies exist, each focusing on different aspects of model training and architecture [2][3].
- Applications range from crowd simulation to autonomous driving, showcasing their versatility across fields [4][5].
- Significant limitations include difficulty in maintaining performance over long horizons and challenges in adapting to dynamic environments [6][7][8].

## Background
World models can be defined as tools that help in both understanding current environments and predicting their future dynamics. There are various frameworks and definitions provided, such as the OpenWorldLib framework that categorizes capabilities and functions of world models [1][6]. Notable researchers, including David Ha and Fei-Fei Li, have contributed greatly to this field, emphasizing the importance of robust and adaptable frameworks [1][5].

## Foundational Definitions and Frameworks  
World models can be segmented into several key functional domains, including:
- **Renderer**, which generates observations from scene descriptions.
- **Simulator**, modeling world dynamics under intervention.
- **Planner** for selecting actionable paths based on defined objectives [1][6].

## Methodological Variations  
Current methodologies in world models differ in architecture and training approaches. Innovations such as sequential latent prediction and generative modeling have emerged, though challenges remain [2][3]. Issues like generalization to real-world scenarios are significant hindrances to effective application [4].

## Key Applications and Evaluations  
World models are operational in various fields:
- In robotics, models have been used to enhance navigation and decision-making through real-time generated scenarios [4].
- Evaluation metrics have evolved to cover multiple dimensions, ultimately focusing on fidelity to real-world dynamics [5][7].

## Trends and Open Problems  
Despite advancements, world models face fundamental limitations:
- Long-horizon reasoning and action conditioning are still developing in various models [3][7].
- Future directions should focus on enhancing integration with external knowledge, ensuring adaptability to new contexts, and maintaining robustness in unpredictable environments [9][10].

## References
[1] Large Action Models: From Inception to Implementation. hf-search. https://huggingface.co/papers/2412.10047 (2024-12-13)
[2] Research on World Models: Not Merely Injecting World Knowledge into Specific Tasks. hf-search. https://huggingface.co/papers/2602.01630 (2026-02-02)
[3] A Definition and Roadmap for World Models. web. https://arxiv.science/abs/2607.06401 (2026-07-07)
[4] Controllable Crowd Generation through World-Model Planning. arxiv. https://arxiv.org/abs/2610.09438 (2026-10-07)
[5] World Models Dream of Success: Diagnosing and Repairing Failure Insensitivity in Robot World Models. arxiv. https://arxiv.org/abs/2610.09134 (2026-10-06)
[6] DriveDreamer: Towards Real-world-driven World Models for Autonomous Driving. hf-daily. https://huggingface.co/papers/2309.09777 (2023-09-18)
[7] State of World Models 2026: Taxonomy, Benchmarks and Open Challenges. web. https://world-models.io/reports/state-of-world-models-2026/state-of-world-models-2026-v1.0.pdf (N/A)
[8] Evaluating World Models with LLMs for Decision Making. web. https://exa.ai/library/publication/vf55stgvgzx (N/A)
[9] Understanding World or Predicting Future? A Comprehensive Survey of World Models. web. https://dl.acm.org/doi/10.1145/3746449 (2025-09-09)
[10] From Generative Engines to Actionable Simulators: The Imperative of Physical Grounding in World Models. hf-search. https://huggingface.co/papers/2601.15533 (2026-01-21)
