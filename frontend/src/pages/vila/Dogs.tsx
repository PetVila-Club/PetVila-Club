import { useState } from 'react';
import { api } from '../../api/client';
import type { Dog } from '../../api/types';
import { Alert, Empty, Spinner } from '../../components/common';
import { DogForm } from '../../components/Forms';
import { SIZE_LABEL } from '../../lib/format';
import { errorMessage, useApi } from '../../lib/useApi';

export default function Dogs() {
  const { data, loading, reload } = useApi<Dog[]>('/me/dogs/');
  const [editing, setEditing] = useState<number | 'new' | null>(null);
  const [error, setError] = useState('');

  const inactivate = async (dog: Dog) => {
    if (!window.confirm(`Inativar ${dog.name}? O histórico de entregas é preservado.`)) return;
    try {
      await api(`/me/dogs/${dog.id}/`, { method: 'DELETE' });
      reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (loading) return <Spinner />;
  const dogs = (data || []).filter((d) => d.is_active);
  return (
    <>
      <div className="list__item">
        <h2 style={{ fontSize: 'var(--step-1)' }}>Meus cães</h2>
        {editing !== 'new' && <button type="button" className="btn btn--sm" onClick={() => setEditing('new')}>Cadastrar cão</button>}
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      {editing === 'new' && (
        <div className="card"><DogForm onSaved={() => { setEditing(null); reload(); }} onCancel={() => setEditing(null)} /></div>
      )}
      {!dogs.length && editing !== 'new' && <Empty title="Nenhum cão cadastrado">Cadastre seu cão para montar o kit dele.</Empty>}
      {dogs.map((dog) => (
        <article className="card stack" key={dog.id}>
          {editing === dog.id ? (
            <DogForm initial={dog} onSaved={() => { setEditing(null); reload(); }} onCancel={() => setEditing(null)} />
          ) : (
            <>
              <div className="list__item">
                <div>
                  <h3>{dog.name}</h3>
                  <p className="small muted">
                    {SIZE_LABEL[dog.size] || 'Porte não informado'} · {dog.weight_kg ? `${dog.weight_kg} kg` : 'peso não informado'} · {dog.age_years !== null ? `${dog.age_years} ano(s)` : 'idade não informada'}
                    {dog.breed ? ` · ${dog.breed}` : ''} · perfil v{dog.profile_version}
                  </p>
                </div>
                <div className="btn-row">
                  <button type="button" className="btn btn--sm btn--ghost" onClick={() => setEditing(dog.id)}>Editar</button>
                  <button type="button" className="btn--link small" onClick={() => inactivate(dog)}>Inativar</button>
                </div>
              </div>
              {dog.missing_fields.length > 0 && <Alert tone="warn">Falta: {dog.missing_fields.join(', ')}.</Alert>}
              <p className="small"><strong>Restrições:</strong> {dog.restrictions_detail.map((t) => t.name).join(', ') || 'nenhuma declarada'}</p>
              <p className="small"><strong>Preferências:</strong> {dog.preferences_detail.map((t) => t.name).join(', ') || '—'}</p>
              {dog.notes && <p className="small muted">{dog.notes}</p>}
            </>
          )}
        </article>
      ))}
    </>
  );
}
