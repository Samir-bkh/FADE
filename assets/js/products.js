/*
 * FADE — catalogue.
 * Pour ajouter un produit : copiez un bloc, changez l'id (lettres, chiffres, tirets),
 * le nom, le prix… "kind" choisit le visuel dessiné automatiquement :
 * nozzle (flacon applicateur), jar (pot), dropper (compte-gouttes), tall (flacon),
 * spray (vaporisateur), box (coffret). "image" remplace le visuel par une photo.
 */
window.FADE_CATEGORIES = [
  { id: "coloration", label: "Coloration", desc: "Semi-permanente, pigments riches." },
  { id: "coiffage", label: "Coiffage", desc: "Cires, pommades, textures." },
  { id: "soin", label: "Soin", desc: "Cheveux et cuir chevelu." },
  { id: "barbe", label: "Barbe", desc: "Huiles et finitions." },
  { id: "coffret", label: "Coffrets", desc: "Les essentiels réunis." }
];

window.FADE_PRODUCTS = [
  {
    id: "coloration-noir",
    name: "Coloration semi-permanente Noir",
    label: ["COLORATION", "SEMI-PERMANENTE"],
    variant: "NOIR",
    category: "coloration",
    price: 14.9,
    size: "100 ml · 3.4 fl.oz",
    kind: "nozzle",
    images: ["assets/img/coloration-noir.jpg"],
    badge: "Best-seller",
    featured: true,
    claims: ["Pigments riches", "Résultat naturel", "Longue tenue"],
    desc: "La coloration utilisée au salon pour redessiner un contour, densifier une barbe ou intensifier un dégradé. Son embout fin permet un tracé précis, ligne par ligne.",
    usage: [
      "Faire un test d'allergie 48 h avant la première utilisation.",
      "Appliquer sur cheveux ou barbe propres et secs à l'aide de l'embout.",
      "Laisser poser 5 à 15 minutes selon l'intensité souhaitée.",
      "Rincer abondamment à l'eau tiède."
    ],
    info: "Usage professionnel – Barber supply. Composition complète indiquée sur l'emballage."
  },
  {
    id: "cire-mate",
    name: "Cire Matte",
    label: ["CIRE", "MATTE"],
    variant: "FIXATION FORTE",
    category: "coiffage",
    price: 12.9,
    size: "100 ml",
    kind: "jar",
    featured: true,
    claims: ["Fini mat", "Tenue forte", "Se recoiffe"],
    desc: "Une cire à l'effet poudré, sans brillance, pour des coiffures texturées qui tiennent toute la journée sans figer.",
    usage: [
      "Chauffer une noisette de produit entre les paumes.",
      "Travailler sur cheveux secs, des racines vers les pointes.",
      "Structurer avec les doigts ou un peigne."
    ],
    info: "Se rince à l'eau. Composition complète indiquée sur l'emballage."
  },
  {
    id: "pommade-brillance",
    name: "Pommade Brillance",
    label: ["POMMADE", "BRILLANCE"],
    variant: "FIXATION MOYENNE",
    category: "coiffage",
    price: 12.9,
    size: "100 ml",
    kind: "jar",
    claims: ["Fini brillant", "Base eau", "Rinçage facile"],
    desc: "Pour les coiffures plaquées, side part et looks classiques. Une brillance nette, une tenue souple.",
    usage: [
      "Appliquer sur cheveux secs ou légèrement humides.",
      "Peigner pour un fini net, retravailler dans la journée si besoin."
    ],
    info: "Composition complète indiquée sur l'emballage."
  },
  {
    id: "poudre-texturisante",
    name: "Poudre Texturisante",
    label: ["POUDRE", "TEXTURISANTE"],
    variant: "VOLUME",
    category: "coiffage",
    price: 11.9,
    size: "20 g",
    kind: "tall",
    featured: true,
    claims: ["Volume instantané", "Invisible", "Fini mat"],
    desc: "Quelques pincées aux racines suffisent pour un volume immédiat et une matière légère, idéale sur cheveux fins.",
    usage: [
      "Saupoudrer directement sur les racines, cheveux secs.",
      "Masser du bout des doigts pour activer la texture."
    ],
    info: "Composition complète indiquée sur l'emballage."
  },
  {
    id: "spray-sel-de-mer",
    name: "Spray Sel de Mer",
    label: ["SPRAY", "SEL DE MER"],
    variant: "TEXTURE",
    category: "coiffage",
    price: 12.9,
    size: "200 ml",
    kind: "spray",
    claims: ["Effet décoiffé", "Pré-coiffant", "Léger"],
    desc: "Le pré-coiffant qui donne du corps et du mouvement avant le séchage. Parfait avant une cire matte.",
    usage: [
      "Vaporiser sur cheveux humides.",
      "Sécher au diffuseur ou à la main pour un effet naturel."
    ],
    info: "Composition complète indiquée sur l'emballage."
  },
  {
    id: "shampoing-quotidien",
    name: "Shampoing Quotidien",
    label: ["SHAMPOING", "QUOTIDIEN"],
    variant: "TOUS CHEVEUX",
    category: "soin",
    price: 11.9,
    size: "250 ml",
    kind: "tall",
    claims: ["Doux", "Usage fréquent", "Cuir chevelu sain"],
    desc: "Un shampoing doux qui nettoie sans assécher, pensé pour un usage quotidien et pour éliminer cires et pommades.",
    usage: [
      "Appliquer sur cheveux mouillés, faire mousser.",
      "Rincer. Renouveler si nécessaire."
    ],
    info: "Composition complète indiquée sur l'emballage."
  },
  {
    id: "huile-a-barbe",
    name: "Huile à Barbe",
    label: ["HUILE", "À BARBE"],
    variant: "NOURRISSANTE",
    category: "barbe",
    price: 13.9,
    size: "30 ml",
    kind: "dropper",
    featured: true,
    claims: ["Nourrit", "Assouplit", "Non grasse"],
    desc: "Discipline et adoucit la barbe, apaise la peau en dessous. Une finition propre après chaque taille.",
    usage: [
      "Déposer 3 à 5 gouttes dans la paume.",
      "Masser dans la barbe jusqu'à la peau, puis peigner."
    ],
    info: "Composition complète indiquée sur l'emballage."
  },
  {
    id: "lotion-apres-rasage",
    name: "Lotion Après-Rasage",
    label: ["LOTION", "APRÈS-RASAGE"],
    variant: "APAISANTE",
    category: "barbe",
    price: 12.9,
    size: "100 ml",
    kind: "spray",
    claims: ["Apaise", "Rafraîchit", "Finition salon"],
    desc: "La finition fraîche du salon, à la maison. Calme le feu du rasoir et laisse la peau nette.",
    usage: [
      "Vaporiser sur la peau propre après le rasage.",
      "Laisser pénétrer sans rincer."
    ],
    info: "Composition complète indiquée sur l'emballage."
  },
  {
    id: "coffret-essentiel",
    name: "Coffret L'Essentiel",
    label: ["COFFRET", "L'ESSENTIEL"],
    variant: "3 PRODUITS",
    category: "coffret",
    price: 34.9,
    compareAt: 41.7,
    size: "Coloration Noir + Cire Matte + Huile à Barbe",
    kind: "box",
    badge: "-16 %",
    featured: false,
    claims: ["Prêt à offrir", "3 best-sellers", "Économie"],
    desc: "Les trois produits les plus demandés au salon, réunis dans un coffret prêt à offrir.",
    usage: [
      "Contient : Coloration semi-permanente Noir 100 ml, Cire Matte 100 ml, Huile à Barbe 30 ml."
    ],
    info: "Voir chaque produit pour le détail d'utilisation."
  }
];
