import "./PopularCategories.css";

const categories = [
  { name: "Plumber", icon: "🔧" },
  { name: "Electrician", icon: "⚡" },
  { name: "HVAC", icon: "❄️" },
  { name: "Dentist", icon: "🦷" },
  { name: "Restaurant", icon: "🍽️" },
  { name: "Lawyer", icon: "⚖️" },
];

export default function PopularCategories({
  activeCategory,
  onCategorySelect,
}) {
  return (
    <div className="popular-categories">
      <p className="popular-title">Popular categories</p>

      <div className="category-list">
        {categories.map((category) => {
          const isActive = activeCategory === category.name;

          return (
            <button
              key={category.name}
              type="button"
              className={`category-chip ${
                isActive ? "category-chip-active" : ""
              }`}
              onClick={() => onCategorySelect(category.name)}
            >
              <span className="category-icon">{category.icon}</span>
              <span>{category.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}