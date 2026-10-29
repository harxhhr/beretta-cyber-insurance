# Beretta: platform + live monitoring

| Folder | What it is |
|---|---|
| `kyh-cyber-insurance/` | **Part 1, the Beretta platform.** Evidence → pricing at inception → bind → the warranty state machine. Owns the premium and the warranties. |
| `kyh-agent/` | **Part 2, live monitoring.** The endpoint agent and the collector. Owns everything about endpoints and sends one signed fleet roll-up per company to Part 1. |
| `integration/` | One test that runs both systems for real and checks the whole chain. |
| `run_linked_demo.py` | Both systems plus four simulated endpoints, for a presentation. |
| `docs/` | Explanation of how the two parts are linked, with screenshots. |

Python 3.9+ standard library only.

```bash
python run_linked_demo.py                                  # then open http://127.0.0.1:8000
python -m unittest discover -s kyh-cyber-insurance/tests -t kyh-cyber-insurance   # 32 tests
python kyh-agent/run_tests.py                              # 155 tests
python integration/test_linked_system.py                   # 1 end-to-end test across both
```

## With a real Windows VM

```bash
python run_linked_demo.py --vm-ip 192.168.56.1     # the laptop's VirtualBox host-only IP
```

The collector then listens on that IP over HTTPS (private CA in `demo-tls/`), the company declares a
fifth endpoint, and `vm-kit/` holds everything the VM needs: share it with the VM and run
`connect-vm.ps1` there, then `kyh-vm-demo.ps1 <action>` to change real settings live. Full steps:
`docs/Beretta_VM_Setup_and_Demo_Guide.pdf`.

The one rule both parts keep: **monitoring never re-prices a bound policy.** Agent and fleet
data change warranty states only.
