type ModuleCardProps = {
  active: boolean;
  title: string;
  description: string;
  onClick: () => void;
};

export function ModuleCard({ active, title, description, onClick }: ModuleCardProps) {
  return (
    <button className={`module-card ${active ? "active" : ""}`} onClick={onClick} type="button">
      <span className="module-title">{title}</span>
      <span className="module-description">{description}</span>
    </button>
  );
}

