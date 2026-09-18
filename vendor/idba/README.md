# IDBA-UD 1.1.3 — adaptation FEVIR

Source : https://github.com/loneknightpy/idba/tree/1.1.3

Archive : https://codeload.github.com/loneknightpy/idba/tar.gz/refs/tags/1.1.3

SHA-256 de `idba-1.1.3.tar.gz` : `6b1746a29884f4fa17b110d94d9ead677ab5557c084a93b16b6a043dbb148709`.

Copyright original : Yu Peng. Licence GPL version 2 ou ultérieure, reproduite dans `COPYING`. L'archive source originale est incluse sans modification.

Modifications FEVIR du 18 septembre 2026, fournies dans `single-end.patch` :

- Option `--single` pour une entrée FASTA de reads indépendants via `-r`.
- Aucune estimation de distance ou recherche de mate en single-end. Un fichier de contigs locaux vide est produit pour permettre les itérations existantes.
- Aucun scaffolding en single-end. Sortie `contig.fa` conservée.
- Rejet des bibliothèques longues ou des bibliothèques supplémentaires appariées avec `--single`.
- Option `--version` identifiant explicitement le binaire modifié.
- Limite de stockage des reads courts portée de 128 à 500 bases, pour les reads Illumina de 150/250/300 bases. Les k-mers restent limités à 124.
- En PE, une bibliothèque sans estimation valide de distance est exclue du scaffolding. Cela évite l'accès à des paramètres inexistants qui faisait planter la version originale sur un jeu trop pauvre pour produire des contigs. Les contigs sont conservés.

Les algorithmes d'assemblage et de correction communs ne sont pas remplacés. Le chemin PE avec une distance valide conserve son fonctionnement ; il a été comparé à la version originale sur un jeu synthétique. Cette adaptation n'est pas une release officielle d'IDBA-UD.

`lib/build_idba.py` vérifie l'archive, applique le correctif puis compile IDBA-UD et fq2fa. Il ne télécharge rien. Commande utilisée pour les binaires Linux x86-64 livrés :

```bash
python3 lib/build_idba.py --static --jobs 4
```

Compilateur : GCC 13.3.0, options `-std=gnu++11 -O3 -fopenmp -pthread -static`.
