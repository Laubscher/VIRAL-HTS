# Bibliothèques des binaires IDBA fournis

Ces fichiers accompagnent `bin/idba_ud` et `bin/fq2fa`, compilés pour Linux x86-64 avec GCC 13.3.0 et l'option `-static`.

## Versions et licences

| Composant | Paquet source utilisé dans l'environnement de compilation | Licence |
| --- | --- | --- |
| glibc : libc, libm, démarrage C et fonctions système | `glibc 2.39-0ubuntu8.6` | Principalement LGPL-2.1-or-later ; autres notices conservées dans `licenses/glibc-LICENSES.txt` |
| libstdc++, libgcc, libgomp et démarrage GCC | `gcc-13 13.3.0-6ubuntu2~24.04` | GPL-3.0-or-later avec GCC Runtime Library Exception 3.1 |

Les archives statiques de GCC proviennent des paquets de développement GCC 13. Les bibliothèques partagées GCC 14 également installées dans cet environnement ne sont pas celles utilisées pour cette liaison statique.

`BUILD-PACKAGES.tsv` contient les versions des paquets. `BUILD-LIBRARIES.tsv` contient les chemins et empreintes des archives et objets présents dans cet environnement. `GCC-LINK-COMMAND.txt` consigne la commande de liaison annoncée par le compilateur pour les mêmes options, à titre d'inventaire ; ce fichier n'est pas un journal de la compilation initiale.

## Fichiers de licence

`licenses/` contient les textes GPL v2, GPL v3 et LGPL v2.1, l'exception GCC 3.1, les notices Ubuntu des paquets utilisés et les fichiers de licence originaux de la glibc. Les notices individuelles restent également dans les sources.

La glibc et son utilisation dans ces exécutables sont couvertes par ses licences. Les destinataires peuvent modifier la bibliothèque et reconstruire les exécutables avec leur version modifiée. Aucune restriction supplémentaire de modification ou de rétro-ingénierie pour le débogage de ces modifications n'est ajoutée.

Les bibliothèques d'exécution GCC bénéficient de l'exception 3.1 pour les compilations admissibles. Le script fourni utilise GCC sur le code source C++, avec ses options ordinaires, sans greffon propriétaire ni traitement d'une représentation intermédiaire par un outil incompatible avec la GPL. Les textes de licence et de l'exception sont conservés ; les sources complètes du compilateur GCC ne sont pas ajoutées à ce complément.

## Sources de la glibc

Le dossier `sources/` contient le paquet source complet `glibc 2.39-0ubuntu8.6` :

- `glibc_2.39.orig.tar.xz` : sources amont ;
- `glibc_2.39.orig.tar.xz.asc` : signature amont conservée ;
- `glibc_2.39-0ubuntu8.6.debian.tar.xz` : modifications et scripts Ubuntu/Debian ;
- `glibc_2.39-0ubuntu8.6.dsc` : descripteur du paquet source.

Références : [GPL v2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html), [LGPL v2.1](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html), [exception GCC 3.1](https://www.gnu.org/licenses/gcc-exception-3.1.html), [paquet source Ubuntu](https://launchpad.net/ubuntu/+source/glibc/2.39-0ubuntu8.6).
