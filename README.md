# FADE Barbers — boutique en ligne

Site e-commerce statique de la marque **FADE** (produits de coiffure de jesuispassechezsouf).
HTML / CSS / JavaScript pur, sans dépendance ni build : il s'héberge n'importe où (GitHub Pages, Netlify, OVH…).

## Fonctionnalités
- Accueil, boutique avec filtres et tri, fiches produit, à propos, contact + FAQ, informations légales (mentions, CGV, confidentialité), page 404.
- Panier (mémorisé dans le navigateur), tiroir panier, barre « ajouter » collante sur mobile.
- Commande : coordonnées, retrait au salon ou livraison (offerte dès 50 €), mode de paiement, note.
- Réception de la commande : récapitulatif envoyé en un clic par **Instagram** (par défaut), **WhatsApp** ou **e-mail**, et en option automatiquement via **Formspree**.
- Mobile d'abord, thème clair/sombre automatique, SEO (balises, sitemap, robots), icône d'application.

## Configurer (à faire une fois)
Tout se règle dans `assets/js/config.js` :
| Clé | Exemple | Effet |
| --- | --- | --- |
| `whatsapp` | `"33612345678"` | affiche le bouton « Envoyer sur WhatsApp » |
| `email` | `"commandes@fade.fr"` | affiche le bouton e-mail |
| `formEndpoint` | `"https://formspree.io/f/xxxx"` | chaque commande arrive par e-mail automatiquement |
| `shipping`, `freeShippingFrom` | | tarifs de livraison |
| `legal` | | SIRET, adresse… pour les mentions légales |

## Produits
`assets/js/products.js` : nom, prix, description, contenance. Les visuels produits sont dessinés
automatiquement au style FADE (`kind`), ou remplacés par une photo via `images: ["assets/img/ma-photo.jpg"]`.
Les prix et produits autres que la coloration Noir sont des exemples à ajuster.

## Mise en ligne (GitHub Pages)
1. Dépôt GitHub → **Settings → Pages** → Source : **GitHub Actions**.
2. Le workflow `.github/workflows/pages.yml` publie le site à chaque push.
3. Adresse : `https://samir-bkh.github.io/FADE/` (ou un nom de domaine perso dans Settings → Pages).

## Tester en local
```
python3 -m http.server 8000
```
puis ouvrir http://localhost:8000
