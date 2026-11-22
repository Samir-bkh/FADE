/*
 * FADE — configuration de la boutique.
 * Modifiez ce fichier pour brancher vos vrais canaux de commande.
 * Aucun autre fichier n'a besoin d'être touché.
 */
window.FADE_CONFIG = {
  brand: "FADE",
  tagline: "Barbers",
  owner: "jesuispassechezsouf",

  // Canaux de réception des commandes ----------------------------------
  // Instagram : utilisé par défaut (fonctionne sans autre réglage).
  instagram: "jesuispassechezsouf",
  // WhatsApp : numéro au format international SANS "+" ni espaces, ex. "33612345678".
  // Laisser vide pour masquer le bouton WhatsApp.
  whatsapp: "",
  // E-mail de réception, ex. "commandes@fade-barbers.fr". Vide = masqué.
  email: "",
  // Optionnel : URL d'un formulaire Formspree (https://formspree.io) pour recevoir
  // chaque commande automatiquement par e-mail, ex. "https://formspree.io/f/abcdwxyz".
  formEndpoint: "",

  // Livraison -----------------------------------------------------------
  currency: "EUR",
  freeShippingFrom: 50, // livraison offerte dès ce montant (€). 0 = désactivé.
  shipping: [
    {
      id: "retrait",
      label: "Retrait au salon",
      desc: "Chez jesuispassechezsouf. On vous confirme le créneau par message.",
      price: 0,
      needsAddress: false
    },
    {
      id: "livraison",
      label: "Livraison à domicile",
      desc: "Colissimo suivi, 2 à 4 jours ouvrés en France métropolitaine.",
      price: 5.9,
      needsAddress: true
    }
  ],
  payment: [
    { id: "remise", label: "Paiement au retrait", desc: "Espèces ou carte au salon.", only: "retrait" },
    { id: "virement", label: "Virement / paiement en ligne", desc: "Lien ou RIB envoyé avec la confirmation de commande." }
  ],

  // Mentions légales (à compléter avant mise en ligne définitive) -------
  legal: {
    company: "FADE Barbers",
    status: "[Forme juridique — ex. micro-entreprise]",
    siret: "[SIRET]",
    address: "[Adresse du siège]",
    publisher: "[Nom du responsable de la publication]",
    host: "GitHub Pages — GitHub, Inc., 88 Colin P Kelly Jr St, San Francisco, CA 94107, USA"
  }
};
