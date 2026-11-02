import { useOutletContext } from 'react-router-dom';
import PlaceholderPanel from '../components/PlaceholderPanel';

export default function WeeklyPage() {
    const { canEdit } = useOutletContext();
    const indicators = canEdit ? 'Volume, Average Price, atau Complain' : 'Volume atau Complain';
    return <PlaceholderPanel icon="▣" title="RINGKASAN MINGGUAN" description="Pilih indikator mingguan dari menu navigasi." message={`Pilih ${indicators}.`} />;
}