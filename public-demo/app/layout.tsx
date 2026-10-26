import type {Metadata} from 'next';
import './style.css';
export const metadata:Metadata={title:'TeacherLens — твоя стратегия в математике',description:'Проверь уравнения, выбери стратегию и попробуй её на практике. A private, browser-local mathematics learning journey.',icons:{icon:'/icon.svg'}};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="ru"><body>{children}</body></html>;}
