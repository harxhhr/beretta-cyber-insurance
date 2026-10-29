// IEEE-style reference list. The report numbers them in order of first citation (build_report.js, cite()).
// Industry reports and specifications are cited as the V2 parameter file cites them; their page and figure
// locators are in kyh-cyber-insurance/app/pricing_v2_params.json.
module.exports = {
  // ---- journal and conference papers (Chapter 2)
  gordon2002: "L. A. Gordon and M. P. Loeb, \"The economics of information security investment,\" ~ACM Transactions on Information and System Security~, vol. 5, no. 4, pp. 438–457, Nov. 2002.",
  anderson2006: "R. Anderson and T. Moore, \"The economics of information security,\" ~Science~, vol. 314, no. 5799, pp. 610–613, Oct. 2006.",
  buhlmann1967: "H. Bühlmann, \"Experience rating and credibility,\" ~ASTIN Bulletin~, vol. 4, no. 3, pp. 199–207, 1967.",
  bohme2010: "R. Böhme and G. Schwartz, \"Modeling cyber-insurance: Towards a unifying framework,\" in ~Proc. 9th Workshop on the Economics of Information Security (WEIS)~, Cambridge, MA, USA, Jun. 2010.",
  shetty2010: "N. Shetty, G. Schwartz, M. Felegyhazi, and J. Walrand, \"Competitive cyber-insurance and Internet security,\" in ~Economics of Information Security and Privacy~, T. Moore, D. Pym, and C. Ioannidis, Eds. Boston, MA, USA: Springer, 2010, pp. 229–247.",
  maillart2010: "T. Maillart and D. Sornette, \"Heavy-tailed distribution of cyber-risks,\" ~The European Physical Journal B~, vol. 75, no. 3, pp. 357–364, 2010.",
  pal2014: "R. Pal, L. Golubchik, K. Psounis, and P. Hui, \"Will cyber-insurance improve network security? A market analysis,\" in ~Proc. IEEE INFOCOM~, Toronto, ON, Canada, 2014, pp. 235–243.",
  biener2015: "C. Biener, M. Eling, and J. H. Wirfs, \"Insurability of cyber risk: An empirical analysis,\" ~The Geneva Papers on Risk and Insurance – Issues and Practice~, vol. 40, no. 1, pp. 131–158, 2015.",
  edwards2016: "B. Edwards, S. Hofmeyr, and S. Forrest, \"Hype and heavy tails: A closer look at data breaches,\" ~Journal of Cybersecurity~, vol. 2, no. 1, pp. 3–14, 2016.",
  eling2016: "M. Eling and W. Schnell, \"What do we know about cyber risk and cyber risk insurance?\" ~The Journal of Risk Finance~, vol. 17, no. 5, pp. 474–491, 2016.",
  wheatley2016: "S. Wheatley, T. Maillart, and D. Sornette, \"The extreme risk of personal data breaches and the erosion of privacy,\" ~The European Physical Journal B~, vol. 89, no. 1, art. 7, 2016.",
  marotta2017: "A. Marotta, F. Martinelli, S. Nanni, A. Orlando, and A. Yautsiukhin, \"Cyber-insurance survey,\" ~Computer Science Review~, vol. 24, pp. 35–61, May 2017.",
  woods2017a: "D. Woods, I. Agrafiotis, J. R. C. Nurse, and S. Creese, \"Mapping the coverage of security controls in cyber insurance proposal forms,\" ~Journal of Internet Services and Applications~, vol. 8, no. 1, art. 8, 2017.",
  woods2017b: "D. Woods and A. Simpson, \"Policy measures and cyber insurance: A framework,\" ~Journal of Cyber Policy~, vol. 2, no. 2, pp. 209–226, 2017.",
  doshi2017: "F. Doshi-Velez and B. Kim, \"Towards a rigorous science of interpretable machine learning,\" arXiv:1702.08608, 2017.",
  talesh2018: "S. A. Talesh, \"Data breach, privacy, and cyber insurance: How insurance companies act as 'compliance managers' for businesses,\" ~Law & Social Inquiry~, vol. 43, no. 2, pp. 417–440, 2018.",
  romanosky2019: "S. Romanosky, L. Ablon, A. Kuehn, and T. Jones, \"Content analysis of cyber insurance policies: How do carriers price cyber risk?\" ~Journal of Cybersecurity~, vol. 5, no. 1, art. tyz002, 2019.",
  eling2019: "M. Eling and J. Wirfs, \"What are the actual costs of cyber risk events?\" ~European Journal of Operational Research~, vol. 272, no. 3, pp. 1109–1119, 2019.",
  dambra2020: "S. Dambra, L. Bilge, and D. Balzarotti, \"SoK: Cyber insurance – technical challenges and a system security roadmap,\" in ~Proc. IEEE Symposium on Security and Privacy (SP)~, San Francisco, CA, USA, 2020, pp. 1367–1383.",
  woods2021: "D. W. Woods, T. Moore, and A. C. Simpson, \"The county fair cyber loss distribution: Drawing inferences from insurance prices,\" ~Digital Threats: Research and Practice~, vol. 2, no. 2, art. 10, 2021.",
  meyer2023: "L. Meyer, S. Romero, G. Bertoli, T. Burt, A. Weinert, and J. L. Ferres, \"How effective is multifactor authentication at deterring cyberattacks?\" arXiv:2305.00945, 2023.",

  // ---- industry data used by the pricing model
  coalition2025: "Coalition, Inc., ~2025 Cyber Claims Report~. San Francisco, CA, USA: Coalition, 2025.",
  netdiligence2025: "NetDiligence, ~Cyber Claims Study 2025~. Gladwyne, PA, USA: NetDiligence, 2025.",
  iris2025: "Cyentia Institute, ~Information Risk Insights Study (IRIS) 2025~. Cyentia Institute, 2025.",
  iris2022: "Cyentia Institute, ~Information Risk Insights Study (IRIS) 2022~. Cyentia Institute, 2022.",
  marsh2023: "Marsh McLennan, ~Using Data to Prioritize Cybersecurity Investments~. New York, NY, USA: Marsh McLennan, 2023.",
  sophos2024: "Sophos, ~The Impact of Compromised Backups on Ransomware Outcomes~. Abingdon, U.K.: Sophos, 2024.",
  ibm2023: "IBM Security and Ponemon Institute, ~Cost of a Data Breach Report 2023~. Armonk, NY, USA: IBM, 2023.",
  ibm2019: "IBM Security and Ponemon Institute, ~Cost of a Data Breach Report 2019~. Armonk, NY, USA: IBM, 2019.",
  naic2026: "National Association of Insurance Commissioners, ~Report on the Cybersecurity Insurance Market~. Kansas City, MO, USA: NAIC, 2026.",
  fitch2024: "Fitch Ratings, US standalone cyber insurance loss ratios, as reported in ~Insurance Journal~, May 2024.",

  // ---- Indian law and regulation
  certin2022: "Indian Computer Emergency Response Team (CERT-In), ~Directions under sub-section (6) of section 70B of the Information Technology Act, 2000 relating to information security practices, procedure, prevention, response and reporting of cyber incidents for Safe & Trusted Internet~, No. 20(3)/2022-CERT-In, New Delhi, India, Apr. 28, 2022.",
  dpdp2023: "Government of India, ~The Digital Personal Data Protection Act, 2023~ (No. 22 of 2023), ~The Gazette of India~, Aug. 11, 2023.",
  irdai2023: "Insurance Regulatory and Development Authority of India, ~IRDAI (Expenses of Management of Insurers transacting General or Health Insurance Business) Regulations, 2023~, Hyderabad, India, 2023.",
  nic2008: "Central Statistics Office, Ministry of Statistics and Programme Implementation, ~National Industrial Classification (All Economic Activities) 2008~. New Delhi, India: Government of India, 2008.",

  // ---- standards
  nistcsf2024: "National Institute of Standards and Technology, ~The NIST Cybersecurity Framework (CSF) 2.0~, NIST CSWP 29, Gaithersburg, MD, USA, Feb. 2024.",
  cis2021: "Center for Internet Security, ~CIS Critical Security Controls, Version 8~. East Greenbush, NY, USA: CIS, 2021.",
  iso27001: "~Information security, cybersecurity and privacy protection – Information security management systems – Requirements~, ISO/IEC 27001:2022, International Organization for Standardization, Geneva, Switzerland, 2022.",
  ieee29148: "~Systems and software engineering – Life cycle processes – Requirements engineering~, ISO/IEC/IEEE 29148:2018, 2018.",
  ieee1016: "~IEEE Standard for Information Technology – Systems Design – Software Design Descriptions~, IEEE Std 1016-2009, 2009.",
  ieee1012: "~IEEE Standard for System, Software, and Hardware Verification and Validation~, IEEE Std 1012-2016, 2016.",
  ieee29119: "~Software and systems engineering – Software testing – Part 1: General concepts~, ISO/IEC/IEEE 29119-1:2022, 2022.",
  ieee754: "~IEEE Standard for Floating-Point Arithmetic~, IEEE Std 754-2019, 2019.",
  rfc2104: "H. Krawczyk, M. Bellare, and R. Canetti, \"HMAC: Keyed-hashing for message authentication,\" IETF RFC 2104, Feb. 1997.",
  fips180: "National Institute of Standards and Technology, ~Secure Hash Standard (SHS)~, FIPS PUB 180-4, Gaithersburg, MD, USA, Aug. 2015.",
  rfc8446: "E. Rescorla, \"The Transport Layer Security (TLS) protocol version 1.3,\" IETF RFC 8446, Aug. 2018.",
  rfc8259: "T. Bray, Ed., \"The JavaScript Object Notation (JSON) data interchange format,\" IETF RFC 8259, Dec. 2017.",
  uml25: "Object Management Group, ~Unified Modeling Language (UML), Version 2.5.1~, OMG Document formal/17-12-05, Dec. 2017.",
};
