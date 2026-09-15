/**
 * VERDÉ — Botanical Lifestyle Data Store
 * Structured data ready for backend API integration (REST or GraphQL)
 */

window.VerdeData = {
  categories: [
    {
      id: 'indoor',
      title: 'Indoor Plants',
      slug: 'indoor-plants',
      image: '/static/asset/images/indoor-plants.jpg',
      itemCount: 42,
      description: 'Air-purifying foliage, shade-tolerant greens, and sculptural living art.'
    },
    {
      id: 'outdoor',
      title: 'Outdoor Plants',
      slug: 'outdoor-plants',
      image: '/static/asset/images/outdoor-plants.jpg',
      itemCount: 28,
      description: 'Hardy patio ferns, balcony perennials, and garden accents.'
    },
    {
      id: 'flowering',
      title: 'Flowering Plants',
      slug: 'flowering-plants',
      image: '/static/asset/images/flowering-plants.jpg',
      itemCount: 19,
      description: 'Elegant seasonal blooms, peace lilies, and fragrant flowering species.'
    },
    {
      id: 'succulents',
      title: 'Succulents',
      slug: 'succulents',
      image: '/static/asset/images/succulents.jpg',
      itemCount: 35,
      description: 'Low-maintenance rosettes, drought-tolerant echeverias, and curated arrangements.'
    }
  ],

  initialCart: [
    {
      id: 'prod-01',
      name: 'Monstera Deliciosa',
      category: 'Indoor Plants',
      price: 65.00,
      quantity: 1,
      image: '/static/asset/images/indoor-plants.jpg',
    },
    {
      id: 'prod-02',
      name: 'Artisan Succulent Bowl',
      category: 'Succulents',
      price: 48.00,
      quantity: 1,
      image: '/static/asset/images/succulents.jpg',
    }
  ],

  searchTags: [
    'Monstera',
    'Peace Lily',
    'Boston Fern',
    'Ceramic Planter',
    'Low Light',
    'Pet Friendly',
    'Echeveria'
  ]
};
