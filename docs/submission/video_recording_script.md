# Video recording script (about 7 minutes)

Record the screen at 1920×1080 with narration (Windows: Xbox Game Bar, Win+Alt+R, or OBS Studio).
Save the file as `deliverables/Group19_Capstone_video.mp4`, then run
`powershell -ExecutionPolicy Bypass -File docs\submission\build_submission_zip.ps1`.

Before recording: close other windows, set the browser zoom to 100%, and run once to make sure the demo starts.

| Time | Show | Do | Say |
|---|---|---|---|
| 0:00 | Poster or slide 1 | — | "We are Group 19. Our project, Beretta, is an explainable cyber-insurance underwriting and continuous monitoring platform for Indian SMEs." |
| 0:20 | Problem Statement slide | — | "Today a small company's cyber premium comes from a questionnaire it fills in once a year. Nobody checks it, the company can't see why the price is what it is, and nothing is watched after the policy is bound." |
| 0:50 | Terminal | `python run_linked_demo.py` | "This starts both systems: the underwriting platform on port 8000 and the monitoring collector on 8443, with four simulated endpoints reporting." |
| 1:15 | Platform, company intake | Open the company page | "The underwriter enters the company: sector from its NIC code, turnover and claims history." |
| 1:40 | Questionnaire / evidence | Scroll the controls | "Every answer is stored with its source and an evidence strength: declared, documented, tested or technically observed. The strongest, most recent evidence wins." |
| 2:20 | Quote | Calculate the premium | "The pricing engine prices five perils from published claims data. Here is the premium, the expected loss per peril, and the effect of each control." |
| 3:00 | Quote, controls and savings | Scroll to what-if savings | "The company can see exactly what verifying each control would save." |
| 3:30 | Collector dashboard | Paste the admin token it printed | "The collector shows each endpoint, labelled SIMULATED, with the evidence behind every check. Reports are signed and numbered, so they can't be forged or replayed." |
| 4:00 | Terminal, then platform | `bind` | "We bind the policy. Its warranties start as MET." |
| 4:20 | Terminal, then both dashboards | `break KAL-PLANT-WS03 edr_down` | "We stop EDR on one machine. Within seconds the EDR warranty moves to IN_GRACE. The premium has not changed." |
| 5:00 | Terminal, platform | `fast-forward` | "Grace periods are in days, so this audited demo step ends the grace period: the warranty is now BREACHED." |
| 5:25 | Terminal, platform | `fix KAL-PLANT-WS03` | "After the fix it goes through REMEDIATED back to MET. The bound premium stayed the same throughout; monitoring never re-prices a policy." |
| 5:55 | Platform as the insured | Switch to the customer role | "The insured sees a read-only view: its premium, the evidence held for each control and how to lower the premium." |
| 6:20 | Terminal | Run the three test commands below | "All 224 automated tests pass: 65 for the platform, 158 for the agent and collector, and one end-to-end test." |
| 6:50 | Poster or Future Extensions slide | — | "Next we want Indian claims data, identity-provider connectors to verify MFA, and a pilot on real company fleets. Thank you." |

Test commands (run from the repository folder):

```bash
python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance
python kyh-agent/run_tests.py
python integration/test_linked_system.py
```

Optional: with the Windows VM running, start `python run_linked_demo.py --vm-ip 192.168.56.1` and show the VM reporting
as a real endpoint (see docs/Beretta_VM_Setup_and_Demo_Guide.pdf).
